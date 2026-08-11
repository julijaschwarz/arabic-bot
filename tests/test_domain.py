from __future__ import annotations

import pytest

from arabic_bot.domain import letters as L
from arabic_bot.domain.digits import DIGITS, to_arabic
from arabic_bot.domain.normalize import normalize_answer, parse_number, split_tokens
from arabic_bot.domain.shaping import shape


def test_alphabet_is_complete():
    assert len(L.LETTERS) == 28
    assert len({letter.id for letter in L.LETTERS}) == 28
    assert len({letter.char for letter in L.LETTERS}) == 28


def test_exactly_six_letters_do_not_connect_forward():
    assert "".join(letter.char for letter in L.NON_CONNECTING) == "اددذرزو".replace("دد", "د")


def test_forms_of_connecting_letter_differ():
    ba = L.BY_ID["ba"]
    assert len({ba.isolated, ba.initial, ba.medial, ba.final}) == 4


def test_non_connecting_letter_has_no_separate_initial_form():
    alif = L.BY_ID["alif"]
    assert alif.initial == alif.isolated
    assert alif.medial == alif.final


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Baa!", "ba"),
        ("Ба-а", "ба"),
        ("bāʼ", "ba"),
        ("  ДЖИИМ  ", "джим"),
        ("нуун", "нун"),
        ("Ёж", "еж"),
    ],
)
def test_normalize_answer(raw, expected):
    assert normalize_answer(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("٣٤٥", 345), ("345", 345), ("семь", 7), ("  0 ", 0), ("ни разу", 0), ("абв", None)],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_split_tokens_handles_commas_and_dashes():
    assert split_tokens("алиф, лям - мим") == ["алиф", "лям", "мим"]


def test_letters_of_word():
    assert [unit.name_ru for unit in L.letters_of("كتاب")] == ["кяф", "та", "алиф", "ба"]


def test_teh_marbuta_is_a_sign_not_a_letter():
    units = L.letters_of("مدرسة")
    assert isinstance(units[-1], L.Sign)
    assert units[-1].name_ru == "та марбута"


def test_hamza_alif_counts_as_alif():
    assert L.letters_of("أسد")[0] is L.BY_ID["alif"]


def test_count_letter():
    assert L.count_letter("ليل", L.BY_ID["lam"]) == 2
    assert L.count_letter("بيت", L.BY_ID["lam"]) == 0


def test_ambiguous_transliteration_resolves_to_several_letters():
    # «ха» — это и ح, и خ, и ه; проверка обязана быть терпимой к этому.
    assert L.resolve_candidates("ха") >= {"ha", "kha", "ha_soft"}
    assert L.resolve_candidates("джим") == {"jim"}


def test_arabic_digits():
    assert to_arabic(345) == "٣٤٥"
    assert [d.char for d in DIGITS][:3] == ["٠", "١", "٢"]
    assert [d.value for d in DIGITS] == list(range(10))


def test_digit_names_are_accepted_in_both_alphabets():
    from arabic_bot.domain.digits import resolve_candidates

    assert 7 in resolve_candidates("сабаа")
    assert 7 in resolve_candidates("sabaa")
    assert 7 in resolve_candidates("Саба")
    assert 3 in resolve_candidates("таляса")
    assert resolve_candidates("абракадабра") == set()


def test_every_digit_has_a_distinct_name():
    names = [d.name_ru for d in DIGITS]
    assert len(set(names)) == 10


def test_shaping_picks_correct_forms():
    glyphs = shape("كتاب")
    assert [g.position for g in glyphs] == ["initial", "medial", "final", "isolated"]


def test_shaping_merges_lam_alef_ligature():
    glyphs = shape("سلام")
    ligature = [g for g in glyphs if len(g.sources) == 2]
    assert len(ligature) == 1
    assert ligature[0].sources == (1, 2)
