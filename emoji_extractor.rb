# Code in this class largely taken from:
#
# - https://github.com/github/gemoji and
# - https://github.com/mattermost/mattermost-webapp

require 'emoji'
require 'fileutils'
require 'mini_magick'
require 'open-uri'

class EmojiExtractor

  SOURCE_PATH = File.join(File.dirname(__FILE__), 'source')
  OUTPUT_PATH = File.join(File.dirname(__FILE__), 'build', 'dump')

  SKIN_TONE_TYPES = {
    "\u{1F3FB}" => 'light skin tone',
    "\u{1F3FC}" => 'medium-light skin tone',
    "\u{1F3FD}" => 'medium skin tone',
    "\u{1F3FE}" => 'medium-dark skin tone',
    "\u{1F3FF}" => 'dark skin tone'
  }.freeze

  SKIN_TONE_MAP = {
    "1" => "\u{1F3FB}",
    "2" => "\u{1F3FC}",
    "3" => "\u{1F3FD}",
    "4" => "\u{1F3FE}",
    "5" => "\u{1F3FF}",
  }.freeze

  GENDER_MAP = {
    "M" => "\u{2642}",
    "W" => "\u{2640}",
  }.freeze

  FAMILY_MAP = {
    "B" => "\u{1f466}",
    "G" => "\u{1f467}",
    "M" => "\u{1f468}",
    "W" => "\u{1f469}",
  }.freeze

  FAMILY = "1F46A".freeze
  COUPLE = "1F491".freeze
  KISS = "1F48F".freeze

  GENDER_MALE = "\u{2642}".freeze
  GENDER_FEMALE = "\u{2640}".freeze
  ZERO_WIDTH_JOINER = "\u{200D}".freeze
  VARIATION_SELECTOR_16 = "\u{FE0F}".freeze

  def initialize(version, size = 160)
    @ttf_file = File.join(SOURCE_PATH, 'Apple Color Emoji.ttc')
    @version = version
    @size = size
  end

  def download_sequences
    puts 'Downloading emoji-sequences.txt...'
    path = File.join(SOURCE_PATH, './emoji-sequences.txt')
    open(path, 'wb') do |file|
      file << open("https://unicode.org/Public/emoji/#{@version}.0/emoji-sequences.txt").read
    end
    @emoji_sequences = File.readlines(path)
  end

  def extract
    puts 'Creating output directory...'
    if File.directory? OUTPUT_PATH
        FileUtils.remove_dir OUTPUT_PATH
    end
    Dir.mkdir OUTPUT_PATH

    puts "Exporting emojis..."
    each do |glyph_name, type, binread|
      if emoji = glyph_name_to_emoji(glyph_name, true)
        image_filename = "#{OUTPUT_PATH}/unicode/emoji_u#{File.basename(emoji.image_filename.gsub(/[\s-]/, '_'))}"
        FileUtils.mkdir_p(File.dirname(image_filename))
        File.open(image_filename, 'wb') { |f| f.write binread.call }

        image = MiniMagick::Image.new(image_filename)
        image.resize "128x128"
      end
    end

    puts "Exporting emojis sequences"
    Emoji.all.clone.each do |emoji|
      next unless emoji.raw

      sequences = emoji_modifier_sequences(emoji.raw.split(''))
      next unless sequences
      sequences.each do |sequence|
        pngbytes = read_png(sequence)
        print '.'
        next unless pngbytes

        modifier = sequence.split('')[1]
        short_name = SKIN_TONE_TYPES[modifier]
        new_name = "#{emoji.name}_#{short_name.gsub(/[\s-]/, '_')}"
        new_emoji = Emoji.create(new_name) do |char|
          char.category = 'skintone'
          char.add_unicode_alias sequence
        end
        new_emoji.image_filename = "emoji_u#{new_emoji.hex_inspect.gsub(/[\s-]/, '_')}.png"

        fullpath = "#{OUTPUT_PATH}/unicode/#{new_emoji.image_filename}"
        unless File.file?(fullpath)
          File.open(fullpath, 'wb') { |f| f.write pngbytes }
        end

        image = MiniMagick::Image.new(fullpath)
        image.resize "128x128"
      end
    end
  end

  private

  def each(&block)
    return to_enum(__method__) unless block_given?

    File.open(@ttf_file, 'rb') do |file|
      font_offsets = parse_ttc(file)
      file.pos = font_offsets[0]

      tables = parse_tables(file)
      glyph_index = extract_glyph_index(file, tables)

      each_glyph_bitmap(file, tables, glyph_index, &block)
    end
  end

  def glyph_name_to_emoji(glyph_name, single)
    zwj = Emoji::ZERO_WIDTH_JOINER
    v16 = Emoji::VARIATION_SELECTOR_16

    if glyph_name =~ /^u(#{FAMILY}|#{COUPLE}|#{KISS})\.([#{FAMILY_MAP.keys.join('')}]+)$/
      if $1 == FAMILY ? $2 == "MWB" : $2 == "WM"
        raw = [$1.hex].pack('U')
      else
        if $1 == COUPLE
          middle = "#{zwj}\u{2764}#{v16}#{zwj}" # heavy black heart
        elsif $1 == KISS
          middle = "#{zwj}\u{2764}#{v16}#{zwj}\u{1F48B}#{zwj}" # heart + kiss mark
        else
          middle = zwj
        end
        raw = $2.split('').map { |c| FAMILY_MAP.fetch(c) }.join(middle)
      end
      candidates = [raw]
    else
      raw = glyph_name.gsub(/(^|_)u([0-9A-F]+)/) { ($1.empty?? $1 : zwj) + [$2.hex].pack('U') }
      raw.sub!(/\.0\b/, '')
      raw.sub!(/\.(#{SKIN_TONE_MAP.keys.join('|')})/) { SKIN_TONE_MAP.fetch($1) }
      raw.sub!(/\.(#{GENDER_MAP.keys.join('|')})$/) { v16 + zwj + GENDER_MAP.fetch($1) }
      candidates = [raw]
      candidates << raw.sub(v16, '') if raw.include?(v16)
      candidates << raw.gsub(zwj, '') if raw.include?(zwj)
      candidates.dup.each { |c| candidates << (c + v16) }
    end

    if single
      candidates.map { |c| Emoji.find_by_unicode(c) }.compact.first
    else
      candidates
    end
  end

  # https://www.microsoft.com/typography/otspec/otff.htm
  def parse_ttc(io)
    header_name = io.read(4).unpack('a*')[0]
    raise unless "ttcf" == header_name
    header_version, num_fonts = io.read(4*2).unpack('l>N')
    io.read(4 * num_fonts).unpack('N*')
  end

  def parse_tables(io)
    sfnt_version, num_tables = io.read(4 + 2*4).unpack('Nn')
    # sfnt_version #=> 0x00010000
    num_tables.times.each_with_object({}) do |_, tables|
      tag, checksum, offset, length = io.read(4 + 4*3).unpack('a4N*')
      tables[tag] = {
        checksum: checksum,
        offset: offset,
        length: length,
      }
    end
  end

  GlyphIndex = Struct.new(:length, :name_index, :names) do
    def name_for(glyph_id)
      index = name_index[glyph_id]
      names[index - 257]
    end

    def each(&block)
      length.times(&block)
    end

    def each_with_name
      each do |glyph_id|
        yield glyph_id, name_for(glyph_id)
      end
    end
  end

  def extract_glyph_index(io, tables)
    postscript_table = tables.fetch('post')
    io.pos = postscript_table[:offset]
    end_pos = io.pos + postscript_table[:length]

    parse_version(io.read(32).unpack('l>')[0]) #=> 2.0
    num_glyphs = io.read(2).unpack('n')[0]
    glyph_name_index = io.read(2*num_glyphs).unpack('n*')

    glyph_names = []
    while io.pos < end_pos
      length = io.read(1).unpack('C')[0]
      glyph_names << io.read(length)
    end

    GlyphIndex.new(num_glyphs, glyph_name_index, glyph_names)
  end

  # https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6sbix.html
  def each_glyph_bitmap(io, tables, glyph_index)
    io.pos = sbix_offset = tables.fetch('sbix')[:offset]
    strike = extract_sbix_strike(io, glyph_index.length, @size)

    glyph_index.each_with_name do |glyph_id, glyph_name|
      glyph_offset = strike[:glyph_data_offset][glyph_id]
      next_glyph_offset = strike[:glyph_data_offset][glyph_id + 1]

      if glyph_offset && next_glyph_offset && glyph_offset < next_glyph_offset
        io.pos = sbix_offset + strike[:offset] + glyph_offset
        x, y, type = io.read(2*2 + 4).unpack('s2A4')
        yield glyph_name, type, -> { io.read(next_glyph_offset - glyph_offset - 8) }
      end
    end
  end

  def extract_sbix_strike(io, num_glyphs, image_size)
    sbix_offset = io.pos
    version, flags, num_strikes = io.read(2*2 + 4).unpack('n2N')
    strike_offsets = num_strikes.times.map { io.read(4).unpack('N')[0] }

    strike_offsets.each do |strike_offset|
      io.pos = sbix_offset + strike_offset
      ppem, resolution = io.read(4*2).unpack('n2')
      next unless ppem == @size

      data_offsets = io.read(4 * (num_glyphs+1)).unpack('N*')
      return {
               ppem: ppem,
               resolution: resolution,
               offset: strike_offset,
               glyph_data_offset: data_offsets,
             }
    end
    return nil
  end

  def read_png(emoji)
    emoji_has_skintone = emoji.split('').map(&:strip).select do |char|
      SKIN_TONE_TYPES.values.include?(char)
    end.any?

    each do |glyph_name, _, binread|
      if emoji_has_skintone
        next unless glyph_name =~ /\.[1-5]($|\.)/
      end
      matches = glyph_name_to_emoji(glyph_name, false)
      next unless matches && (matches.include?(emoji) || matches.include?(emoji + "\u{fe0f 200d 2640}"))
      return binread.call
    end
    nil
  end

  def all_emoji_modifier_bases
    return if @emoji_sequences.nil?
    match_string = '; Emoji_Modifier_Sequence   ;'
    lines = @emoji_sequences.select { |l| l.include?(match_string) }
    hex_strings = lines.map { |l| /^[0-9A-F]{4,5}/.match(l)[0] }
    integers = hex_strings.map { |s| s.to_i(16) }
    integers.map { |i| [i].pack('U') }
  end

  def emoji_modifier_base?(code_point)
    all_emoji_modifier_bases.include?(code_point)
  end

  def emoji_modifier_sequences(emoji_modifier_chars)
    return nil unless emoji_modifier_base?(emoji_modifier_chars[0])

    if emoji_modifier_chars.include?(GENDER_MALE)
      sequences = SKIN_TONE_TYPES.each_key.map do |skin_tone_modifier|
        [emoji_modifier_chars[0],
         skin_tone_modifier,
         ZERO_WIDTH_JOINER,
         GENDER_MALE,
         VARIATION_SELECTOR_16].join('')
      end
    else
      sequences = SKIN_TONE_TYPES.each_key.map do |skin_tone_modifier|
        [emoji_modifier_chars[0], skin_tone_modifier].join('')
      end

      # Add female-specific sequences and see if they exist in the system font
      # by returning nil from the AppleEmojiExtractor
      sequences << SKIN_TONE_TYPES.each_key.map do |skin_tone_modifier|
        [emoji_modifier_chars[0],
         skin_tone_modifier,
         ZERO_WIDTH_JOINER,
         GENDER_FEMALE,
         VARIATION_SELECTOR_16].join('')
      end

      sequences.flatten!
    end

    sequences
  end

  def parse_version(num)
    major = num >> 16
    minor = num & 0xFFFF
    "#{major}.#{minor}"
  end
end
