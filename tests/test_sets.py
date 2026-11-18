"""Tests for saving card sets (R10) and the card history (R11) in the logic module (no Flask)."""
import json
import os
from datetime import datetime

import pytest

from flashcards import MAX_SETS, Card, CardSet, add_set, find_set, load_sets, remove_set, save_sets

CELL = [Card("Cell", "The basic unit of life.")]
TWO = [Card("Osmosis", "Movement of water across a membrane."), Card("Enzyme", "A protein.")]
NOV_1 = datetime(2026, 11, 1, 9, 0, 0)
NOV_2 = datetime(2026, 11, 2, 9, 0, 0)


def day(n):
    return datetime(2026, 11, n, 9, 0, 0)


def filenames(sets):
    return [s.filename for s in sets]


# ---------- R10: save every set between visits ----------

def test_R10_sets_load_back_in_order(tmp_path):
    path = tmp_path / "cards.json"
    sets = add_set(add_set([], "a.pdf", CELL, NOV_1), "b.pdf", TWO, NOV_2)
    save_sets(path, sets)
    assert load_sets(path) == sets


def test_R10_save_file_is_a_json_list_of_sets(tmp_path):
    path = tmp_path / "cards.json"
    sets = add_set([], "a.pdf", CELL, NOV_1)
    save_sets(path, sets)
    assert json.loads(path.read_text(encoding="utf-8")) == {"sets": [{
        "id": sets[0].id,
        "filename": "a.pdf",
        "uploaded": "2026-11-01T09:00:00",
        "cards": [{"term": "Cell", "definition": "The basic unit of life."}],
    }]}


def test_R10_save_creates_missing_folder_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "new folder" / "cards.json"
    save_sets(path, add_set([], "a.pdf", CELL, NOV_1))
    assert [f.name for f in path.parent.iterdir()] == ["cards.json"]


def test_R10_non_ascii_text_survives_saving(tmp_path):
    path = tmp_path / "cards.json"
    sets = add_set([], "été.pdf", [Card("Ölçü", "Größe – “quoted” • bullet")], NOV_1)
    save_sets(path, sets)
    assert load_sets(path) == sets


def test_R10_old_one_set_file_loads_as_a_single_set(tmp_path):
    path = tmp_path / "cards.json"
    path.write_text(json.dumps({
        "filename": "unit.pdf",
        "cards": [{"term": "Cell", "definition": "The basic unit of life."}],
    }), encoding="utf-8")
    mtime = datetime(2026, 10, 5, 14, 30, 0)
    os.utime(path, (mtime.timestamp(), mtime.timestamp()))
    [only] = load_sets(path)
    assert only.filename == "unit.pdf"
    assert only.cards == CELL
    assert only.uploaded == mtime  # the old format has no date; the file's time is the best guess
    assert only.id


def test_R10_loading_an_old_file_does_not_rewrite_it(tmp_path):
    path = tmp_path / "cards.json"
    text = json.dumps({"filename": "unit.pdf", "cards": [{"term": "Cell", "definition": "x"}]})
    path.write_text(text, encoding="utf-8")
    load_sets(path)
    assert path.read_text(encoding="utf-8") == text


def test_R10_missing_file_loads_no_sets(tmp_path):
    assert load_sets(tmp_path / "nothing.json") == []


@pytest.mark.parametrize("content", [
    "not json",
    "",
    "[]",
    "{}",
    '{"sets": 3}',
    '{"filename": "a.pdf"}',
    '{"filename": "a.pdf", "cards": [{"term": "Cell"}]}',
    '{"filename": 3, "cards": []}',
    '{"filename": "a.pdf", "cards": []}',
])
def test_R10_broken_or_empty_file_loads_no_sets(tmp_path, content):
    path = tmp_path / "cards.json"
    path.write_text(content, encoding="utf-8")
    assert load_sets(path) == []


def test_R10_a_broken_set_is_skipped_and_the_others_kept(tmp_path):
    path = tmp_path / "cards.json"
    good = {"id": "a" * 32, "filename": "good.pdf", "uploaded": "2026-11-01T09:00:00",
            "cards": [{"term": "Cell", "definition": "The basic unit of life."}]}
    path.write_text(json.dumps({"sets": [
        {"id": "b" * 32, "filename": "no-date.pdf", "cards": good["cards"]},
        {**good, "id": "c" * 32, "filename": "no-cards.pdf", "cards": []},
        {**good, "id": "d" * 32, "uploaded": "yesterday"},
        "not a set",
        good,
    ]}), encoding="utf-8")
    assert load_sets(path) == [CardSet("a" * 32, "good.pdf", NOV_1, CELL)]


# ---------- R11: card history ----------

def test_R11_new_set_goes_first_with_its_date_and_cards():
    sets = add_set(add_set([], "a.pdf", CELL, NOV_1), "b.pdf", TWO, NOV_2)
    assert filenames(sets) == ["b.pdf", "a.pdf"]
    assert sets[0].uploaded == NOV_2
    assert sets[0].cards == TWO


def test_R11_add_set_does_not_change_the_old_list():
    old = add_set([], "a.pdf", CELL, NOV_1)
    add_set(old, "b.pdf", TWO, NOV_2)
    assert filenames(old) == ["a.pdf"]


def test_R11_each_set_gets_its_own_id():
    sets = []
    for n in range(1, 6):
        sets = add_set(sets, f"{n}.pdf", CELL, day(n))
    assert len({s.id for s in sets}) == 5


def test_R11_eleventh_set_removes_the_oldest():
    sets = []
    for n in range(1, 12):
        sets = add_set(sets, f"unit{n}.pdf", CELL, day(n))
    assert MAX_SETS == 10
    assert filenames(sets) == [f"unit{n}.pdf" for n in range(11, 1, -1)]


def test_R11_same_file_name_updates_the_set_and_moves_it_to_the_top():
    sets = add_set(add_set(add_set([], "a.pdf", CELL, day(1)), "b.pdf", CELL, day(2)), "c.pdf", CELL, day(3))
    old_id = find_set(sets, sets[2].id).id
    sets = add_set(sets, "a.pdf", TWO, day(4))
    assert filenames(sets) == ["a.pdf", "c.pdf", "b.pdf"]
    assert sets[0] == CardSet(old_id, "a.pdf", day(4), TWO)


def test_R11_same_file_name_with_ten_sets_drops_nothing():
    sets = []
    for n in range(1, 11):
        sets = add_set(sets, f"unit{n}.pdf", CELL, day(n))
    sets = add_set(sets, "unit1.pdf", TWO, day(11))
    assert len(sets) == 10
    assert filenames(sets)[0] == "unit1.pdf"
    assert "unit2.pdf" in filenames(sets)


def test_R11_file_names_differing_only_in_case_are_different_sets():
    sets = add_set(add_set([], "Unit.pdf", CELL, NOV_1), "unit.pdf", TWO, NOV_2)
    assert filenames(sets) == ["unit.pdf", "Unit.pdf"]


def test_R11_remove_set_removes_only_that_set():
    sets = add_set(add_set([], "a.pdf", CELL, NOV_1), "b.pdf", TWO, NOV_2)
    assert filenames(remove_set(sets, sets[1].id)) == ["b.pdf"]
    assert filenames(sets) == ["b.pdf", "a.pdf"]


def test_R11_remove_or_find_unknown_id_changes_nothing():
    sets = add_set([], "a.pdf", CELL, NOV_1)
    assert remove_set(sets, "nope") == sets
    assert find_set(sets, "nope") is None
    assert find_set(sets, None) is None


def test_R11_loading_keeps_at_most_ten_sets(tmp_path):
    path = tmp_path / "cards.json"
    raw = [{"id": f"{n:032x}", "filename": f"unit{n}.pdf", "uploaded": day(n).isoformat(),
            "cards": [{"term": "Cell", "definition": "x"}]} for n in range(12, 0, -1)]
    path.write_text(json.dumps({"sets": raw}), encoding="utf-8")
    assert filenames(load_sets(path)) == [f"unit{n}.pdf" for n in range(12, 2, -1)]
