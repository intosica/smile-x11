"""Kaomoji for the Kaomoji tab: group -> list of (text, space separated search tags)."""
KAOMOJI_GROUPS = {
    'joy': [
        ('(^_^)', 'happy smile'), ('(＾▽＾)', 'happy glad'), ('(≧▽≦)', 'excited happy'), ('(*^‿^*)', 'smile cute'),
        ('ヽ(´▽`)/', 'cheer yay'), ('(๑˃ᴗ˂)ﻭ', 'cheer proud'), ('٩(◕‿◕)۶', 'joy happy'), ('(⌒‿⌒)', 'smile content'),
        ('\\(^o^)/', 'banzai hooray yay'), ('(｡◕‿◕｡)', 'cute happy'), ('(☞ﾟヮﾟ)☞', 'point you'), ('☜(ﾟヮﾟ☜)', 'point'),
        ('ᕕ( ᐛ )ᕗ', 'walk run happy'), ('(•‿•)', 'smile'), ('(ᵔᴥᵔ)', 'dog cute happy'), ('(¬‿¬)', 'smirk sly'),
    ],
    'love': [
        ('(♥‿♥)', 'love heart'), ('(◕‿◕)♡', 'love cute'), ('(*´▽`*)♡', 'love'), ('(づ｡◕‿‿◕｡)づ', 'hug love'),
        ('(っ´▽`)っ', 'hug'), ('(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)', 'blush shy love'), ('(´,,•ω•,,)♡', 'love cute'), ('(*˘︶˘*).｡*♡', 'love happy'),
        ('(´∀`)♡', 'love'), ('(•ө•)♡', 'kiss love'), ('(︶｡︶)', 'kiss'), ('(๑>◡<๑)', 'blush cute'),
    ],
    'sadness': [
        ('(T_T)', 'cry sad'), ('(;_;)', 'cry sad'), ('(╥﹏╥)', 'cry sad'), ('(ಥ_ಥ)', 'cry sad'),
        ('(._.)', 'sad'), ('(︶︹︺)', 'sad'), ('｡･ﾟﾟ*(>д<)*ﾟﾟ･｡', 'sob cry loud'), ('(つ﹏⊂)', 'cry sad'),
        ('(´;ω;`)', 'cry sad'), ('(ノ_<。)', 'cry sad'), ('(︿︿)', 'sad down'), ('(´-ω-`)', 'tired sad'),
    ],
    'anger': [
        ('(╬ಠ益ಠ)', 'angry rage'), ('(ಠ_ಠ)', 'disapproval stare'), ('(ノಠ益ಠ)ノ彡┻━┻', 'table flip angry rage'),
        ('(╯°□°)╯︵ ┻━┻', 'table flip angry'), ('┬─┬ノ( º _ ºノ)', 'table put back calm'), ('(ง •̀_•́)ง', 'fight ready'),
        ('(`皿´＃)', 'angry'), ('(¬_¬)', 'annoyed unamused'), ('ヽ(`Д´)ﾉ', 'angry'), ('(҂`з´)', 'angry'),
        ('(︶︿︶)', 'grumpy'), ('(ꐦ ´Д`)', 'angry'),
    ],
    'surprise': [
        ('(°o°)', 'shock surprised'), ('(⊙_⊙)', 'shock stare'), ('(◎_◎)', 'surprised'), ('Σ(ﾟДﾟ)', 'shock'),
        ('(O_O)', 'shock'), ('(ﾟдﾟ)', 'shock'), ('w(°ｏ°)w', 'shock surprised'), ('(°ロ°)', 'shock'),
        ('(☉_☉)', 'stare'), ('ヽ(°〇°)ﾉ', 'surprised'),
    ],
    'greeting': [
        ('(｡･∀･)ﾉﾞ', 'hello hi wave'), ('(^-^)/', 'hello wave'), ('ヾ(•ω•`)o', 'hello hi'), ('(•◡•)/', 'hi hello'),
        ('(^o^)ノ', 'bye wave'), ('(´• ω •`)ﾉ', 'bye'), ('_(._.)_', 'bow sorry thanks'), ('m(_ _)m', 'bow sorry thanks'),
        ('(ゝ∀･)b', 'thumbs up good'), ('(b ᵔ▽ᵔ)b', 'thumbs up'), ('o7', 'salute'), ('(￣▽￣)ゞ', 'salute'),
    ],
    'shrug': [
        ('¯\\_(ツ)_/¯', 'shrug dunno idk'), ('┐(´д`)┌', 'shrug whatever'), ('┐(￣ヘ￣)┌', 'shrug'), ('ʅ(°ᴗ°)ʃ', 'shrug'),
        ('¯\\(°_o)/¯', 'shrug dunno'), ('(´･_･`)', 'confused'), ('(・_・ヾ', 'confused'), ('(?_?)', 'confused'),
        ('(・・？)', 'confused question'), ('(⌒_⌒;)', 'nervous sweat'), ('(^_^;)', 'nervous sweat awkward'), ('(;一_一)', 'unimpressed'),
    ],
    'action': [
        ('(ง°ل͜°)ง', 'fight'), ('(҂‾ ▵‾)︻デ═一', 'shoot gun'), ('(☞ ͡° ͜ʖ ͡°)☞', 'lenny point'), ('( ͡° ͜ʖ ͡°)', 'lenny face'),
        ('(∩ ͡° ͜ʖ ͡°)⊃━☆ﾟ.*', 'magic'), ('(∩｀-´)⊃━☆ﾟ.*･｡ﾟ', 'magic wizard'), ('(っ˘ڡ˘ς)', 'yummy tasty'), ('( ˘▽˘)っ♨', 'tea drink'),
        ('(ᗒᗣᗕ)՞', 'scared'), ('(＾• ω •＾)', 'cat cute'), ('(=^･ω･^=)', 'cat'), ('ʕ•ᴥ•ʔ', 'bear cute'),
        ('(◕ᴥ◕ʋ)', 'dog'), ('(ᵔ.ᵔ)', 'cute'), ('(-_-) zzZ', 'sleep tired'), ('(￣ρ￣)..zzZZ', 'sleep'),
    ],
}

GROUP_LABELS = {'recent': '🕒', 'joy': '😄', 'love': '♥', 'sadness': '😢', 'anger': '😠', 'surprise': '😮',
                'greeting': '👋', 'shrug': '🤷', 'action': '⚡'}
