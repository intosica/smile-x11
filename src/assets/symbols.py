"""Symbol groups for the Symbols tab. Search uses the Unicode character names (unicodedata)."""
import unicodedata

SYMBOL_GROUPS = {
    'punctuation': '¡¿‽…•·–—‘’‚“”„«»‹›§¶†‡′″※‰‱¦|¨¯´`˜^~',
    'currency': '$€£¥¢₹₽₩₪₺₴₿₫₱฿¤₡₦₲₵',
    'math': '±×÷=≠≈≡≤≥<>∞√∛∑∏∫∂∆∇π°%¬∧∨∩∪∈∉∋⊂⊃⊆⊇∀∃∄∴∵∝∅⊕⊗⊥∥∠',
    'arrows': '←↑→↓↔↕↖↗↘↙⇐⇑⇒⇓⇔⇕↩↪↵↺↻⟵⟶⟷➔➜➤➡⬅⬆⬇',
    'shapes': '■□▪▫▲△▼▽◀▶◆◇○●◎◉◌★☆✦✧❖♠♣♥♦♤♧♡♢',
    'marks': '✓✔✗✘✕✖✚✱✲✳❀❁✿❤☀☁☂☃☎☏✉☑☒⚠⚡♻☮☯☸☺☹☻♪♫♬♩',
    'latin': 'àáâãäåæçèéêëìíîïñòóôõöøœùúûüýÿßÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØŒÙÚÛÜÝþðŁłŠšŽž',
    'numbers': '¹²³⁴⁵⁶⁷⁸⁹⁰₀₁₂₃₄₅₆₇₈₉¼½¾⅓⅔⅛⅜⅝⅞ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ',
    'greek': 'αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ',
}


def symbol_name(ch: str) -> str:
    return unicodedata.name(ch, '').lower()

GROUP_LABELS = {'recent': '🕒', 'punctuation': '¶', 'currency': '€', 'math': '±', 'arrows': '→', 'shapes': '◆',
                'marks': '✓', 'latin': 'é', 'numbers': '½', 'greek': 'Ω'}
