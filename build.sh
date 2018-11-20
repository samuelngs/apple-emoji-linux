#!/usr/bin/env ruby

require_relative './lib/extractor.rb'

unicode_version = 11

emoji_extractor = EmojiExtractor.new(unicode_version, 160)
emoji_extractor.download_sequences
emoji_extractor.extract!

%x(echo hi)
