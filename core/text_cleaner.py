# core/text_cleaner.py
import re
import emoji
import pandas as pd
import pyarabic.araby as ar
import functools
import operator

def clean_arabic_text(text):
    """
    تنظيف النص العربي (خاصة العامية المصرية) دون تجذير.
    تزيل الروابط، التشكيل، التطويل، الإيموجي، وتوحد الحروف.
    """
    if pd.isna(text) or not isinstance(text, str):
        return ""

    text = re.sub(r'^https?:\/\/.*[\r\n]*', '', text, flags=re.MULTILINE)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r"^\d+\W+|\b\d+\b|\W+\d+$", "", text)

    text = ar.strip_tashkeel(text)
    text = ar.strip_tatweel(text)
    text = text.replace("#", " ").replace("@", " ").replace("_", " ")

    # تفكيك الإيموجي إلى نصوص (تبقى فارغة أو رموز وصفية)
    em_split_emoji = emoji.get_emoji_regexp().split(text)
    em_split_whitespace = [substr.split() for substr in em_split_emoji]
    text = " ".join(functools.reduce(operator.concat, em_split_whitespace))
    text = re.sub(r'(.)\1+', r'\1\1', text)   # تقليل التكرار (رااائع → رائع)

    # توحيد الحروف
    text = text.replace("آ", "ا").replace("إ", "ا").replace("أ", "ا")
    text = text.replace("ؤ", "و").replace("ئ", "ي")

    return text.strip()