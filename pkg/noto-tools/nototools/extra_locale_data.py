#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Extra locale data that's still missing from CLDR."""

__author__ = 'roozbeh@google.com (Roozbeh Pournader)'

LIKELY_SUBTAGS = {
    'abr': ('abr', 'Latn', 'GH'),  # Abron
    'abq': ('abq', 'Cyrl', 'RU'),  # Abaza
    'ada': ('ada', 'Latn', 'GH'),  # Adangme
    'ae': ('ae', 'Avst', 'ZZ'),  # Avestan
    'aeb': ('aeb', 'Arab', 'TN'),  # Tunisian Arabic
    'aii': ('aii', 'Syrc', 'IQ'),  # Assyrian Neo-Aramaic
    'ain': ('ain', 'Kana', 'JP'),  # Ainu
    'akk': ('akk', 'Xsux', 'ZZ'),  # Akkadian
    'akz': ('akz', 'Latn', 'US'),  # Alabama
    'ale': ('ale', 'Latn', 'US'),  # Aleut
    'aln': ('aln', 'Latn', 'XK'),  # Gheg Albanian
    'an': ('an', 'Latn', 'ES'),  # Aragonese
    'anp': ('anp', 'Deva', 'IN'),  # Angika
    'arc': ('arc', 'Armi', 'ZZ'),  # Imperial Aramaic
    'aro': ('aro', 'Latn', 'BO'),  # Araona
    'arp': ('arp', 'Latn', 'US'),  # Arapaho
    'arq': ('arq', 'Arab', 'DZ'),  # Algerian Arabic
    'arw': ('arw', 'Latn', 'GY'),  # Arawak
    'ary': ('ary', 'Arab', 'MA'),  # Moroccan Arabic
    'arz': ('arz', 'Arab', 'EG'),  # Egyptian Arabic
    'avk': ('avk', 'Latn', '001'),  # Kotava
    'azb': ('azb', 'Arab', 'IR'),  # Southern Azerbaijani
    'bar': ('bar', 'Latn', 'AT'),  # Bavarian
    'ber': ('ber', 'Arab', 'MA'),  # Berber
    'bej': ('bej', 'Arab', 'SD'),  # Beja
    'bci': ('bci', 'Latn', 'CI'),  # Baoulé
    'bgc': ('bgc', 'Deva', 'IN'),  # Haryanvi
    'bhi': ('bhi', 'Deva', 'IN'),  # Bhilali
    'bhk': ('bhk', 'Latn', 'PH'),  # Albay Bikol
    'bla': ('bla', 'Latn', 'CA'),  # Blackfoot
    'blt': ('blt', 'Tavt', 'VN'),  # Tai Dam
    'bpy': ('bpy', 'Beng', 'IN'),  # Bishnupriya
    'bqi': ('bqi', 'Arab', 'IR'),  # Bakhtiari
    'bsq': ('bsq', 'Bass', 'LR'),  # Bassa
    'bzx': ('bzx', 'Latn', 'ML'),  # Kelengaxo Bozo
    'cad': ('cad', 'Latn', 'US'),  # Caddo
    'car': ('car', 'Latn', 'VE'),  # Galibi Carib
    'cay': ('cay', 'Latn', 'CA'),  # Cayuga
    'chn': ('chn', 'Latn', 'US'),  # Chinook Jargon
    'cho': ('cho', 'Latn', 'US'),  # Choctaw
    'chy': ('chy', 'Latn', 'US'),  # Cheyenne
    'cjs': ('cjs', 'Cyrl', 'RU'),  # Shor
    'ckt': ('ckt', 'Cyrl', 'RU'),  # Chukchi
    'cop': ('cop', 'Copt', 'EG'),  # Coptic
    'cpf': ('cpf', 'Latn', 'HT'),  # Creoles, French
    'cps': ('cps', 'Latn', 'PH'),  # Capiznon
    'crh': ('crh', 'Latn', 'UA'),  # Crimean Tatar
    'crs': ('crs', 'Latn', 'SC'),  # Seselwa Creole French
    'ctd': ('ctd', 'Latn', 'MM'),  # Tedim Chin
    'dak': ('dak', 'Latn', 'US'),  # Dakota
    'dcc': ('dcc', 'Arab', 'IN'),  # Deccan
    'del': ('del', 'Latn', 'US'),  # Delaware
    'din': ('din', 'Latn', 'SS'),  # Dinka
    'dng': ('dng', 'Cyrl', 'KG'),  # Dungan
    'dtp': ('dtp', 'Latn', 'MY'),  # Central Dusun
    'egl': ('egl', 'Latn', 'IT'),  # Emilian
    'egy': ('egy', 'Egyp', 'ZZ'),  # Ancient Egyptian
    'eka': ('eka', 'Latn', 'NG'),  # Ekajuk
    'eky': ('eky', 'Kali', 'TH'),  # Eastern Kayah
    'esu': ('esu', 'Latn', 'US'),  # Central Yupik
    'ett': ('ett', 'Ital', 'IT'),  # Etruscan
    'evn': ('evn', 'Latn', 'CN'),  # Evenki
    'ext': ('ext', 'Latn', 'ES'),  # Extremaduran
    'ffm': ('ffm', 'Latn', 'ML'),  # Maasina Fulfulde
    'frc': ('frc', 'Latn', 'US'),  # Cajun French
    'frr': ('frr', 'Latn', 'DE'),  # Northern Frisian
    'frs': ('frs', 'Latn', 'DE'),  # Eastern Frisian
    'fud': ('fud', 'Latn', 'WF'),  # East Futuna
    'fuq': ('fuq', 'Latn', 'NE'),  # Central-Eastern Niger Fulfulde
    'fuv': ('fuv', 'Latn', 'NG'),  # Nigerian Fulfulde
    'gan': ('gan', 'Hans', 'CN'),  # Gan Chinese
    'gay': ('gay', 'Latn', 'ID'),  # Gayo
    'gba': ('gba', 'Latn', 'CF'),  # Gbaya
    'gbz': ('gbz', 'Arab', 'IR'),  # Zoroastrian Dari
    'gld': ('gld', 'Cyrl', 'RU'),  # Nanai
    'gom': ('gom', 'Deva', 'IN'),  # Goan Konkani
    'got': ('got', 'Goth', 'ZZ'),  # Gothic
    'grb': ('grb', 'Latn', 'LR'),  # Grebo
    'grc': ('grc', 'Grek', 'ZZ'),  # Ancient Greek
    'guc': ('guc', 'Latn', 'CO'),  # Wayuu
    'gur': ('gur', 'Latn', 'GH'),  # Frafra
    'hai': ('hai', 'Latn', 'CA'),  # Haida
    'hak': ('hak', 'Hant', 'CN'),  # Hakka Chinese
    'haz': ('haz', 'Arab', 'AF'),  # Hazaragi
    'hif': ('hif', 'Deva', 'FJ'),  # Fiji Hindi
    'hit': ('hit', 'Xsux', 'ZZ'),  # Hittite
    'hmd': ('hmd', 'Plrd', 'CN'),  # A-Hmao
    'hmn': ('hmn', 'Latn', 'CN'),  # Hmong
    'hnj': ('hnj', 'Latn', 'LA'),  # Hmong Njua
    'hno': ('hno', 'Arab', 'PK'),  # Northern Hindko
    'hop': ('hop', 'Latn', 'US'),  # Hopi
    'hsn': ('hsn', 'Hans', 'CN'),  # Xiang Chinese
    'hup': ('hup', 'Latn', 'US'),  # Hupa
    'hz': ('hz', 'Latn', 'NA'),  # Herero
    'iba': ('iba', 'Latn', 'MY'),  # Iban
    'ikt': ('ikt', 'Latn', 'CA'),  # Inuinnaqtun
    'izh': ('izh', 'Latn', 'RU'),  # Ingrian
    'jam': ('jam', 'Latn', 'JM'),  # Jamaican Creole English
    'jpr': ('jpr', 'Hebr', 'IL'),  # Judeo-Persian
    'jrb': ('jrb', 'Hebr', 'IL'),  # Jedeo-Arabic
    'jut': ('jut', 'Latn', 'DK'),  # Jutish
    'kac': ('kac', 'Latn', 'MM'),  # Kachin
    'kca': ('kca', 'Cyrl', 'RU'),  # Khanty
    'kfy': ('kfy', 'Deva', 'IN'),  # Kumaoni
    'kjh': ('kjh', 'Cyrl', 'RU'),  # Khakas
    'kkh': ('kkh', 'Lana', 'MM'),  # Khün
    'khn': ('khn', 'Deva', 'IN'),  # Khandesi
    'kiu': ('kiu', 'Latn', 'TR'),  # Kirmanjki
    'kpy': ('kpy', 'Cyrl', 'RU'),  # Koryak
    'kr': ('kr', 'Arab', 'NG'),  # Kanuri
    'krj': ('krj', 'Latn', 'PH'),  # Kinaray-a
    'kut': ('kut', 'Latn', 'CA'),  # Kutenai
    'kxm': ('kxm', 'Thai', 'TH'),  # Northern Khmer
    'kyu': ('kyu', 'Kali', 'MM'),  # Western Kayah
    'lab': ('lab', 'Lina', 'ZZ'),  # Linear A
    'lad': ('lad', 'Latn', 'IL'),  # Ladino
    'lam': ('lam', 'Latn', 'ZM'),  # Lamba
    'laj': ('laj', 'Latn', 'UG'),  # Lango
    'lfn': ('lfn', 'Latn', '001'),  # Lingua Franca Nova
    'lij': ('lij', 'Latn', 'IT'),  # Ligurian
    'liv': ('liv', 'Latn', 'LV'),  # Livonian
    'ljp': ('ljp', 'Latn', 'ID'),  # Lampung Api
    'lrc': ('lrc', 'Arab', 'IR'),  # Northern Luri
    'ltg': ('ltg', 'Latn', 'LV'),  # Latgalian
    'lui': ('lui', 'Latn', 'US'),  # Luiseno
    'lun': ('lun', 'Latn', 'ZM'),  # Lunda
    'lus': ('lus', 'Latn', 'IN'),  # Mizo
    'lut': ('lut', 'Latn', 'US'),  # Lushootseed
    'lzh': ('lzh', 'Hant', 'CN'),  # Literary Chinese
    'lzz': ('lzz', 'Latn', 'TR'),  # Laz
    'mdt': ('mdt', 'Latn', 'CG'),  # Mbere
    'mfa': ('mfa', 'Arab', 'TH'),  # Pattani Malay
    'mic': ('mic', 'Latn', 'CA'),  # Micmac
    'mnc': ('mnc', 'Mong', 'CN'),  # Manchu
    'mns': ('mns', 'Cyrl', 'RU'),  # Mansi
    'mro': ('mro', 'Mroo', 'BD'),  # Mru (dlf, also Latn?)
    'mtr': ('mtr', 'Deva', 'IN'),  # Mewari
    'mus': ('mus', 'Latn', 'US'),  # Creek
    'mwl': ('mwl', 'Latn', 'PT'),  # Mirandese
    'mwv': ('mwv', 'Latn', 'ID'),  # Mentawai
    'myx': ('myx', 'Latn', 'UG'),  # Masaaba
    'myz': ('myz', 'Mand', 'ZZ'),  # Classical Mandaic
    'mzn': ('mzn', 'Arab', 'IR'),  # Mazanderani
    'nan': ('nan', 'Latn', 'CN'),  # Min Nan Chinese
    'ndc': ('ndc', 'Latn', 'MZ'),  # Ndau
    'ngl': ('ngl', 'Latn', 'MZ'),  # Lomwe
    'nia': ('nia', 'Latn', 'ID'),  # Nias
    'njo': ('njo', 'Latn', 'IN'),  # Ao Naga
    'noe': ('noe', 'Deva', 'IN'),  # Nimadi
    'nog': ('nog', 'Cyrl', 'RU'),  # Nogai
    'non': ('non', 'Runr', 'ZZ'),  # Old Norse
    'nov': ('nov', 'Latn', '001'),  # Novial
    'nyo': ('nyo', 'Latn', 'UG'),  # Nyoro
    'nzi': ('nzi', 'Latn', 'GH'),  # Nzima
    'ohu': ('ohu', 'Hung', 'HR'),  # Old Hungarian
    'oj': ('oj', 'Latn', 'CA'),  # Ojibwa
    'osa': ('osa', 'Latn', 'US'),  # Osage
    'osc': ('osc', 'Ital', 'ZZ'),  # Oscan
    'otk': ('otk', 'Orkh', 'ZZ'),  # Old Turkish
    'pal': ('pal', 'Phli', 'ZZ'),  # Pahlavi FIXME: should really be 'Phlv'
    'pcd': ('pcd', 'Latn', 'FR'),  # Picard
    'pdc': ('pdc', 'Latn', 'US'),  # Pennsylvania German
    'pdt': ('pdt', 'Latn', 'CA'),  # Plautdietsch
    'peo': ('peo', 'Xpeo', 'ZZ'),  # Old Persian
    'pfl': ('pfl', 'Latn', 'DE'),  # Palatine German
    'phn': ('phn', 'Phnx', 'ZZ'),  # Phoenician
    'pi': ('pi', 'Brah', 'ZZ'),  # Pali
    'pms': ('pms', 'Latn', 'IT'),  # Piedmontese
    'pnt': ('pnt', 'Grek', 'GR'),  # Pontic
    'prs': ('prs', 'Arab', 'AF'),  # Dari
    'qug': ('qug', 'Latn', 'EC'),  # Chimborazo Highland Quichua
    'rom': ('rom', 'Latn', 'RO'),  # Romany
    'sck': ('sck', 'Deva', 'IN'),  # Sadri
    'skr': ('skr', 'Arab', 'PK'),  # Seraiki
    'sou': ('sou', 'Thai', 'TH'),  # Southern Thai
    'swv': ('swv', 'Deva', 'IN'),  # Shekhawati
    'tab': ('tab', 'Cyrl', 'RU'),  # Tabassaran (dlf)
    'ude': ('ude', 'Cyrl', 'RU'),  # Udihe (dlf)
    'uga': ('uga', 'Ugar', 'ZZ'),  # Ugaritic
    'vep': ('vep', 'Latn', 'RU'),  # Veps
    'vmw': ('vmw', 'Latn', 'MZ'),  # Makhuwa
    'wbr': ('wbr', 'Deva', 'IN'),  # Wagdi
    'wbq': ('wbq', 'Telu', 'IN'),  # Waddar
    'wls': ('wls', 'Latn', 'WF'),  # Wallisian
    'wtm': ('wtm', 'Deva', 'IN'),  # Mewati
    'yrk': ('yrk', 'Cyrl', 'RU'),  # Nenets (dlf)
    'xnr': ('xnr', 'Deva', 'IN'),  # Kangri
    'xum': ('xum', 'Ital', 'ZZ'),  # Umbrian (dlf)
    'zdj': ('zdj', 'Arab', 'KM'),  # Ngazidja Comorian
    'und-Mult': ('skr', 'Mult', 'ZZ'), # ancient writing system for Saraiki,
                                       # Arabic now used
    'und-Hung': ('ohu', 'Hung', 'ZZ'), # Old Hungarian, Carpathian basin
    'und-Hluw': ('hlu', 'Hluw', 'ZZ'), # Hieroglyphic Luwian
    'und-Ahom': ('aho', 'Ahom', 'ZZ'), # Ahom
}


ENGLISH_SCRIPT_NAMES = {
    'Cans': u'Canadian Aboriginal', # shorten name for display purposes,
                                    #match Noto font name
}

ENGLISH_LANGUAGE_NAMES = {
    'abr': u'Abron',
    'abq': u'Abaza',
    'aho': u'Ahom',
    'aii': u'Assyrian Neo-Aramaic',
    'akz': u'Alabama',
    'amo': u'Amo',
    'aoz': u'Uab Meto',
    'atj': u'Atikamekw',
    'bap': u'Bantawa',
    'bci': u'Baoulé',
    'ber': u'Berber',
    'bft': u'Balti',
    'bfy': u'Bagheli',
    'bgc': u'Haryanvi',
    'bgx': u'Balkan Gagauz Turkish',
    'bh': u'Bihari',
    'bhb': u'Bhili',
    'bhi': u'Bhilali',
    'bhk': u'Albay Bikol',
    'bjj': u'Kanauji',
    'bku': u'Buhid',
    'blt': u'Tai Dam',
    'bmq': u'Bomu',
    'bqi': u'Bakhtiari',
    'bqv': u'Koro Wachi',
    'bsq': u'Bassa',
    'bto': u'Rinconada Bikol',
    'btv': u'Bateri',
    'buc': u'Bushi',
    'bvb': u'Bube',
    'bya': u'Batak',
    'bze': u'Jenaama Bozo',
    'bzx': u'Kelengaxo Bozo',
    'ccp': u'Chakma',
    'cja': u'Western Cham',
    'cjs': u'Shor',
    'cjm': u'Eastern Cham',
    'ckt': u'Chukchi',
    'cpf': u'French-based Creoles',
    'crj': u'Southern East Cree',
    'crk': u'Plains Cree',
    'crl': u'Northern East Cree',
    'crm': u'Moose Cree',
    'crs': u'Seselwa Creole French',
    'csw': u'Swampy Cree',
    'ctd': u'Tedim Chin',
    'dcc': u'Deccan',
    'dng': u'Dungan',
    'dnj': u'Dan',
    'dtm': u'Tomo Kan Dogon',
    'eky': u'Eastern Kayah',
    'ett': u'Etruscan',
    'evn': u'Evenki',
    'ffm': u'Maasina Fulfulde',
    'fud': u'East Futuna',
    'fuq': u'Central-Eastern Niger Fulfulde',
    'fuv': u'Nigerian Fulfulde',
    'gbm': u'Garhwali',
    'gcr': u'Guianese Creole French',
    'ggn': u'Eastern Gurung',
    'gjk': u'Kachi Koli',
    'gju': u'Gujari',
    'gld': u'Nanai',
    'gos': u'Gronings',
    'grt': u'Garo',
    'gub': u'Guajajára',
    'gvr': u'Western Gurung',
    'haz': u'Hazaragi',
    'hlu': u'Hieroglyphic Luwian',
    'hmd': u'A-Hmao',
    'hnd': u'Southern Hindko',
    'hne': u'Chhattisgarhi',
    'hnj': u'Hmong Njua',
    'hnn': u'Hanunoo',
    'hno': u'Northern Hindko',
    'hoc': u'Ho',
    'hoj': u'Haroti',
    'hop': u'Hopi',
    'ikt': u'Inuinnaqtun',
    'jml': u'Jumli',
    'kao': u'Xaasongaxango',
    'kca': u'Khanty',
    'kck': u'Kalanga',
    'kdt': u'Kuy',
    'kfr': u'Kachchi',
    'kfy': u'Kumaoni',
    'kge': u'Komering',
    'khb': u'Lü',
    'khn': u'Khandesi',
    'kht': u'Khamti',
    'kjg': u'Khmu',
    'kjh': u'Khakas',
    'kkh': u'Khün',
    'kpy': u'Koryak',
    'kvr': u'Kerinci',
    'kvx': u'Parkari Koli',
    'kxm': u'Northern Khmer',
    'kxp': u'Wadiyara Koli',
    'kyu': u'Western Kayah',
    'lab': u'Linear A',
    'laj': u'Lango',
    'lbe': u'Lak',
    'lbw': u'Tolaki',
    'lcp': u'Western Lawa',
    'lep': u'Lepcha',
    'lif': u'Limbu',
    'lis': u'Lisu',
    'ljp': u'Lampung Api',
    'lki': u'Laki',
    'lmn': u'Lambadi',
    'lrc': u'Northern Luri',
    'lut': u'Lushootseed',
    'luz': u'Southern Luri',
    'lwl': u'Eastern Lawa',
    'maz': u'Central Mazahua',
    'mdh': u'Maguindanaon',
    'mdt': u'Mbere',
    'mfa': u'Pattani Malay',
    'mgp': u'Eastern Magar',
    'mgy': u'Mbunga',
    'mns': u'Mansi',
    'mnw': u'Mon',
    'moe': u'Montagnais',
    'mrd': u'Western Magar',
    'mro': u'Mru',
    'mru': u'Cameroon Mono',
    'mtr': u'Mewari',
    'mvy': u'Indus Kohistani',
    'mwk': u'Kita Maninkakan',
    'mxc': u'Manyika',
    'myx': u'Masaaba',
    'myz': u'Classical Mandaic',
    'nch': u'Central Huasteca Nahuatl',
    'ndc': u'Ndau',
    'ngl': u'Lomwe',
    'nhe': u'Eastern Huasteca Nahuatl',
    'nhw': u'Western Huasteca Nahuatl',
    'nij': u'Ngaju',
    'nod': u'Northern Thai',
    'noe': u'Nimadi',
    'nsk': u'Naskapi',
    'nxq': u'Naxi',
    'ohu': u'Old Hungarian',
    'osc': u'Oscan',
    'otk': u'Old Turkish',
    'pcm': u'Nigerian Pidgin',
    'pka': u'Ardhamāgadhī Prākrit',
    'pko': u'Pökoot',
    'pra': u'Prakrit', # language family name
    'prd': u'Parsi-Dari',
    'prs': u'Dari',
    'puu': u'Punu',
    'rcf': u'Réunion Creole French',
    'rej': u'Rejang',
    'ria': u'Riang',  # (India)
    'rjs': u'Rajbanshi',
    'rkt': u'Rangpuri',
    'rmf': u'Kalo Finnish Romani',
    'rmo': u'Sinte Romani',
    'rmt': u'Domari',
    'rmu': u'Tavringer Romani',
    'rng': u'Ronga',
    'rob': u'Tae’',
    'ryu': u'Central Okinawan',
    'saf': u'Safaliba',
    'sck': u'Sadri',
    'scs': u'North Slavey',
    'sdh': u'Southern Kurdish',
    'sef': u'Cebaara Senoufo',
    'skr': u'Seraiki',
    'smp': u'Samaritan',
    'sou': u'Southern Thai',
    'srb': u'Sora',
    'srx': u'Sirmauri',
    'swv': u'Shekhawati',
    'sxn': u'Sangir',
    'syi': u'Seki',
    'syl': u'Sylheti',
    'tab': u'Tabassaran',
    'taj': u'Eastern Tamang',
    'tbw': u'Tagbanwa',
    'tdd': u'Tai Nüa',
    'tdg': u'Western Tamang',
    'tdh': u'Thulung',
    'thl': u'Dangaura Tharu',
    'thq': u'Kochila Tharu',
    'thr': u'Rana Tharu',
    'tkt': u'Kathoriya Tharu',
    'tli': u'Tlingit',
    'tsf': u'Southwestern Tamang',
    'tsg': u'Tausug',
    'tsj': u'Tshangla',
    'ttj': u'Tooro',
    'tts': u'Northeastern Thai',
    'ude': u'Udihe',
    'uli': u'Ulithian',
    'unr': u'Mundari',
    'unx': u'Munda',
    'vic': u'Virgin Islands Creole English',
    'vmw': u'Makhu',
    'wbr': u'Wagdi',
    'wbq': u'Waddar',
    'wls': u'Wallisian',
    'wtm': u'Mewati',
    'xav': u'Xavánte',
    'xcr': u'Carian',
    'xlc': u'Lycian',
    'xld': u'Lydian',
    'xmn': u'Manichaean Middle Persian',
    'xmr': u'Meroitic',
    'xna': u'Ancient North Arabian',
    'xnr': u'Kangri',
    'xpr': u'Parthian',
    'xsa': u'Sabaean',
    'xsr': u'Sherpa',
    'xum': u'Umbrian',
    'yrk': u'Nenets',
    'yua': u'Yucatec Maya',
    'zdj': u'Ngazidja Comorian',
    'zmi': u'Negeri Sembilan Malay',
}

# Supplement mapping of languages to scripts
LANG_TO_SCRIPTS = {
    'ber': ['Arab', 'Latn', 'Tfng'],
    'hak': ['Hans', 'Hant', 'Latn'],
    'nan': ['Hans', 'Hant', 'Latn'],
    'yue': ['Hant'],
}

# Supplement mapping of regions to lang_scripts
REGION_TO_LANG_SCRIPTS = {
    'CN': ['hak-Hans', 'hak-Latn', 'nan-Hans', 'nan-Latn', 'yue-Hans'],
    'HK': ['yue-Hant'],
    'MN': ['mn-Mong'],
    'MY': ['zh-Hans'],
    'TW': ['hak-Hant', 'hak-Latn', 'nan-Hant', 'nan-Latn'],
}

PARENT_LOCALES = {
    'ky-Latn': 'root',
    'sd-Deva': 'root',
    'tg-Arab': 'root',
    'ug-Cyrl': 'root',
}

NATIVE_NAMES = {
    'mn-Mong': u'ᠮᠣᠨᠭᠭᠣᠯ ᠬᠡᠯᠡ',
}

EXEMPLARS = {
  'und-Avst': r'[\U010b00-\U010b35]',
  'und-Bali': r'[\u1b05-\u1b33]',
  'und-Bamu': r'[\ua6a0-\ua6ef]',
  'und-Cham': r'[\uaa00-\uaa28 \uaa50-\uaa59]',
  'und-Copt': r'[\u2c80-\u2cb1]',
  'und-Egyp': r'[\U013000-\U01303f]',
  'und-Hira': r'[\u3041-\u3096\u3099-\u309f\U01b000-\U01b001]',
  'und-Java': r'[\ua984-\ua9b2]',
  'und-Kali': r'[\ua90a-\ua925 \ua900-\ua909]',
  'und-Kana': r'[\u30a0-\u30ff \u31f0-\u31ff]',
  'und-Khar': r'[\U010a10-\U010a13\U010a15-\U010a17\U010a19-\U010a33'
              r'\U010A38-\U010a3a]',
  'und-Kthi': r'[\U11080-\U110C1]',
  'und-Lana': r'[\u1a20-\u1a4c]',
  'und-Lepc': r'[\u1c00-\u1c23]',
  'und-Linb': r'[\U010000-\U01000b \U010080-\U01009f]',
  'und-Mand': r'[\u0840-\u0858]',
  'und-Mtei': r'[\uabc0-\uabe2]',
  'und-Orkh': r'[\U010c00-\U010c48]',
  'und-Phag': r'[\ua840-\ua877]',
  'und-Saur': r'[\ua882-\ua8b3]',
  'und-Sund': r'[\u1b83-\u1ba0]',
  'und-Sylo': r'[\ua800-\ua82b]',
  'und-Tavt': r'[\uaa80-\uaaaf \uaadb-\uaadf]',
  'und-Tglg': r'[\u1700-\u170c \u170e-\u1711]',
  'und-Ugar': r'[\U010380-\U01039d \U01039f]',
  'und-Xsux': r'[\U012000-\U01202f]',
  'und-Zsye': r'[\u2049\u231a\u231b\u2600\u260e\u2614\u2615\u26fa\u2708\u2709'
              r'\u270f\u3297\U01f004\U01f170\U01f193\U01f197\U01f30d\U01f318'
              r'\U01f332\U01f334\U01f335\U01f344\U01f346\U01f352\U01f381'
              r'\U01f393\U01f3a7\U01f3b8\U01f3e1\U01f402\U01f40a\U01f418'
              r'\U01f419\U01f41b\U01f41f\U01f422\U01f424\U01f427\U01f44c'
              r'\U01f44d\U01f453\U01f463\U01f4bb\U01f4ce\U01f4d3\U01f4d6'
              r'\U01f4e1\U01f4fb\U01f511\U01f525\U01f565\U01F63a\U01f680'
              r'\U01f681\U01f683\U01f686\U01f68c\U01f6a2\U01f6a3\U01f6b4]',
  'und-Zsym': r'[\u20ac\u20b9\u2103\u2109\u2115\u2116\u211a\u211e\u2122'
              r'\u21d0-\u21d3\u2203\u2205\u2207\u2208\u220f\u221e\u2248\u2284'
              r'\u231a\u23e3\u23f3\u2400\u2460\u24b6\u2523\u2533\u2602\u260e'
              r'\u2615\u261c\u2637\u263a\u264f\u2656\u2663\u266b'
              r'\u267b\u267f\u26f9\u2708\u2740\u2762\u2a6b\u2a93\u2a64\u2e19'
              r'\u4dc3\U010137\U01017B\U0101ef\U01d122\U01d15e\U01d161]'
}
