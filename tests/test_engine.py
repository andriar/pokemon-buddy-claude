"""Unit tests for buddy-update.py core logic.

Run with: pytest tests/ -v

Covers:
  - Pure functions: XP math, detect_xp, bar rendering, streak, titles, evolution, milestones
  - I/O round-trips: stats file, collection file, buddy file, catch system
"""

import importlib.util
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

# ── Import engine (hyphenated filename, can't use plain import) ───────────────
_ENGINE_PATH = Path(__file__).resolve().parent.parent / "buddy-update.py"
spec = importlib.util.spec_from_file_location("buddy_update", _ENGINE_PATH)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


# ── XP math ───────────────────────────────────────────────────────────────────

class TestXpForLevel(unittest.TestCase):
    def test_level_1_is_zero(self):
        self.assertEqual(engine.xp_for_level(1), 0)

    def test_level_2_is_100(self):
        self.assertEqual(engine.xp_for_level(2), 100)

    def test_level_15_boundary(self):
        # Last level in the (n-1)*100 range
        self.assertEqual(engine.xp_for_level(15), 1400)

    def test_level_16_starts_second_tier(self):
        # 1400 + (16-15)*150 = 1550
        self.assertEqual(engine.xp_for_level(16), 1550)

    def test_level_35_boundary(self):
        # 1400 + (35-15)*150 = 1400 + 3000 = 4400
        self.assertEqual(engine.xp_for_level(35), 4400)

    def test_level_36_starts_third_tier(self):
        # 4400 + (36-35)*200 = 4600
        self.assertEqual(engine.xp_for_level(36), 4600)

    def test_level_50(self):
        # 4400 + (50-35)*200 = 4400 + 3000 = 7400
        self.assertEqual(engine.xp_for_level(50), 7400)


class TestLevelFromXp(unittest.TestCase):
    def test_zero_xp_is_level_1(self):
        self.assertEqual(engine.level_from_xp(0), 1)

    def test_99_xp_is_level_1(self):
        self.assertEqual(engine.level_from_xp(99), 1)

    def test_100_xp_is_level_2(self):
        self.assertEqual(engine.level_from_xp(100), 2)

    def test_boundary_lv15(self):
        self.assertEqual(engine.level_from_xp(1400), 15)

    def test_boundary_lv16(self):
        self.assertEqual(engine.level_from_xp(1550), 16)

    def test_boundary_lv35(self):
        self.assertEqual(engine.level_from_xp(4400), 35)

    def test_boundary_lv36(self):
        self.assertEqual(engine.level_from_xp(4600), 36)

    def test_xp_floor_round_trip(self):
        """xp_for_level(n) should produce exactly level n."""
        for lv in [1, 5, 10, 15, 16, 20, 35, 36, 50]:
            with self.subTest(lv=lv):
                self.assertEqual(engine.level_from_xp(engine.xp_for_level(lv)), lv)

    def test_one_below_threshold_stays_lower(self):
        """One XP below a level threshold stays at the previous level."""
        for lv in [2, 5, 16, 36]:
            threshold = engine.xp_for_level(lv)
            with self.subTest(lv=lv):
                self.assertEqual(engine.level_from_xp(threshold - 1), lv - 1)


# ── XP detection ─────────────────────────────────────────────────────────────

class TestDetectXp(unittest.TestCase):
    def test_explicit_xp_override(self):
        self.assertEqual(engine.detect_xp("gave 75 XP for this"), 75)

    def test_deploy_is_100(self):
        self.assertEqual(engine.detect_xp("deployed to production"), 100)

    def test_ship_is_100(self):
        self.assertEqual(engine.detect_xp("shipped the release"), 100)

    def test_feature_is_50(self):
        self.assertEqual(engine.detect_xp("feature complete"), 50)

    def test_bug_fix_is_10(self):
        self.assertEqual(engine.detect_xp("fixed a bug in the login flow"), 10)

    def test_test_writing_is_30(self):
        self.assertEqual(engine.detect_xp("wrote unit tests for auth module"), 30)

    def test_refactor_is_20(self):
        self.assertEqual(engine.detect_xp("refactor the user component"), 20)

    def test_unknown_defaults_to_10(self):
        self.assertEqual(engine.detect_xp("did some stuff"), 10)

    def test_bahasa_indonesia_deploy(self):
        self.assertEqual(engine.detect_xp("rilis ke produksi"), 100)

    def test_bahasa_indonesia_bug(self):
        self.assertEqual(engine.detect_xp("perbaiki bug login"), 10)

    def test_highest_xp_wins(self):
        # "deploy" (100) and "bug" (10) — higher rule wins
        self.assertEqual(engine.detect_xp("deployed a bugfix to production"), 100)


# ── Bar rendering ─────────────────────────────────────────────────────────────

class TestBar(unittest.TestCase):
    def test_empty_bar(self):
        self.assertEqual(engine.bar(0, 10, 10), '░' * 10)

    def test_full_bar(self):
        self.assertEqual(engine.bar(10, 10, 10), '█' * 10)

    def test_half_bar(self):
        self.assertEqual(engine.bar(5, 10, 10), '█████░░░░░')

    def test_overflow_clamps(self):
        result = engine.bar(20, 10, 10)
        self.assertEqual(result, '█' * 10)

    def test_zero_max_returns_empty(self):
        self.assertEqual(engine.bar(5, 0, 10), '░' * 10)


# ── Streak logic ─────────────────────────────────────────────────────────────

class TestUpdateStreak(unittest.TestCase):
    def _stats(self, streak=0, last_date=''):
        return {'streak': streak, 'last_xp_date': last_date, 'longest_streak': streak}

    def test_first_ever_award_starts_streak(self):
        stats = self._stats()
        bonus, count, is_new = engine.update_streak(stats)
        self.assertTrue(is_new)
        self.assertEqual(count, 1)
        self.assertEqual(bonus, engine.STREAK_BONUS_XP)

    def test_same_day_no_change(self):
        today = engine.TODAY
        stats = self._stats(streak=3, last_date=today)
        bonus, count, is_new = engine.update_streak(stats)
        self.assertFalse(is_new)
        self.assertEqual(count, 3)
        self.assertEqual(bonus, 0)

    def test_consecutive_day_extends_streak(self):
        yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        stats = self._stats(streak=4, last_date=yesterday)
        bonus, count, is_new = engine.update_streak(stats)
        self.assertTrue(is_new)
        self.assertEqual(count, 5)

    def test_gap_resets_streak_to_1(self):
        two_days_ago = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        stats = self._stats(streak=10, last_date=two_days_ago)
        bonus, count, is_new = engine.update_streak(stats)
        self.assertTrue(is_new)
        self.assertEqual(count, 1)

    def test_longest_streak_updated(self):
        yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        stats = self._stats(streak=9, last_date=yesterday)
        stats['longest_streak'] = 9
        engine.update_streak(stats)
        self.assertEqual(stats['longest_streak'], 10)

    def test_longest_streak_not_reduced(self):
        two_days_ago = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        stats = self._stats(streak=10, last_date=two_days_ago)
        stats['longest_streak'] = 10
        engine.update_streak(stats)
        self.assertEqual(stats['longest_streak'], 10)  # not reset to 1


# ── Trainer title ─────────────────────────────────────────────────────────────

class TestGetTrainerTitle(unittest.TestCase):
    def _empty_stats(self):
        return {
            'caught_mythical': False, 'caught_legendary': False,
            'caught_shiny': False, 'ships': 0, 'streak': 0,
            'bug_fixes': 0, 'features': 0,
        }

    def _col(self, n=0):
        return {'pokemon': [{}] * n}

    def test_rookie_with_no_achievements(self):
        self.assertEqual(engine.get_trainer_title(self._empty_stats(), self._col(0)), 'Rookie Trainer')

    def test_mythical_master_beats_all(self):
        stats = self._empty_stats()
        stats['caught_mythical'] = True
        stats['caught_legendary'] = True
        self.assertEqual(engine.get_trainer_title(stats, self._col(35)), 'Mythical Master')

    def test_legend_hunter(self):
        stats = self._empty_stats()
        stats['caught_legendary'] = True
        self.assertEqual(engine.get_trainer_title(stats, self._col()), 'Legend Hunter')

    def test_shiny_chaser(self):
        stats = self._empty_stats()
        stats['caught_shiny'] = True
        self.assertEqual(engine.get_trainer_title(stats, self._col()), 'Shiny Chaser')

    def test_shipmaster(self):
        stats = self._empty_stats()
        stats['ships'] = 1
        self.assertEqual(engine.get_trainer_title(stats, self._col()), 'Shipmaster')

    def test_elite_deployer_at_3_ships(self):
        stats = self._empty_stats()
        stats['ships'] = 3
        self.assertEqual(engine.get_trainer_title(stats, self._col()), 'Elite Deployer')


# ── Evolution ─────────────────────────────────────────────────────────────────

class TestEvolution(unittest.TestCase):
    """Verify evolution thresholds fire at the right levels."""

    def _evolve(self, buddy, old_xp, add_xp):
        old_level = engine.level_from_xp(old_xp)
        new_xp = old_xp + add_xp
        new_level = engine.level_from_xp(new_xp)
        evolutions = engine.STARTER_DATA[buddy]['evolutions']
        target_stage = buddy
        for evo_name, threshold, _ in evolutions:
            if new_level >= threshold:
                target_stage = evo_name
        old_stage = buddy
        for evo_name, threshold, _ in evolutions:
            if old_level >= threshold:
                old_stage = evo_name
        evolved = target_stage if target_stage != old_stage else ''
        return old_stage, target_stage, evolved

    def test_charmander_stays_before_16(self):
        _, stage, evolved = self._evolve('Charmander', 0, engine.xp_for_level(15))
        self.assertEqual(stage, 'Charmander')
        self.assertFalse(evolved)

    def test_charmander_evolves_at_16(self):
        xp_15 = engine.xp_for_level(15)
        needed = engine.xp_for_level(16) - xp_15
        _, stage, evolved = self._evolve('Charmander', xp_15, needed)
        self.assertEqual(stage, 'Charmeleon')
        self.assertTrue(evolved)

    def test_charmeleon_evolves_to_charizard_at_36(self):
        xp_35 = engine.xp_for_level(35)
        needed = engine.xp_for_level(36) - xp_35
        _, stage, evolved = self._evolve('Charmander', xp_35, needed)
        self.assertEqual(stage, 'Charizard')
        self.assertTrue(evolved)

    def test_bulbasaur_evolves_at_16(self):
        xp_15 = engine.xp_for_level(15)
        needed = engine.xp_for_level(16) - xp_15
        _, stage, evolved = self._evolve('Bulbasaur', xp_15, needed)
        self.assertEqual(stage, 'Ivysaur')
        self.assertTrue(evolved)

    def test_squirtle_evolves_at_16(self):
        xp_15 = engine.xp_for_level(15)
        needed = engine.xp_for_level(16) - xp_15
        _, stage, evolved = self._evolve('Squirtle', xp_15, needed)
        self.assertEqual(stage, 'Wartortle')
        self.assertTrue(evolved)


# ── Milestone checks ──────────────────────────────────────────────────────────

class TestCheckMilestones(unittest.TestCase):
    def _stats(self):
        return {
            'milestones': set(), 'streak': 0,
            'caught_legendary': False, 'caught_mythical': False, 'caught_shiny': False,
        }

    def _col(self, n=0):
        return {'pokemon': [{'rarity': 'common'}] * n}

    def test_first_catch_milestone(self):
        col = self._col(1)
        ms = engine.check_milestones(self._stats(), col, 1, 1, None, '')
        names = [m[1] for m in ms]
        self.assertIn('First Catch', names)

    def test_level_10_milestone(self):
        ms = engine.check_milestones(self._stats(), self._col(), 9, 10, None, '')
        names = [m[1] for m in ms]
        self.assertIn('Lv.10 Reached', names)

    def test_level_10_not_triggered_without_crossing(self):
        ms = engine.check_milestones(self._stats(), self._col(), 10, 10, None, '')
        names = [m[1] for m in ms]
        self.assertNotIn('Lv.10 Reached', names)

    def test_no_duplicate_milestones(self):
        stats = self._stats()
        stats['milestones'].add('level_10')
        ms = engine.check_milestones(stats, self._col(), 9, 10, None, '')
        names = [m[1] for m in ms]
        self.assertNotIn('Lv.10 Reached', names)

    def test_streak_7_milestone(self):
        stats = self._stats()
        stats['streak'] = 7
        ms = engine.check_milestones(stats, self._col(), 1, 1, None, '')
        names = [m[1] for m in ms]
        self.assertIn('7-Day Streak', names)

    def test_legendary_catch_milestone(self):
        stats = self._stats()
        catch = ('legendary', 'Mewtwo', 'Psychic', '🧬', False)
        ms = engine.check_milestones(stats, self._col(1), 1, 1, catch, '')
        names = [m[1] for m in ms]
        self.assertIn('Legend Seeker', names)

    def test_shiny_catch_milestone(self):
        stats = self._stats()
        catch = ('common', 'Pikachu', 'Electric', '⚡', True)  # is_shiny=True
        ms = engine.check_milestones(stats, self._col(1), 1, 1, catch, '')
        names = [m[1] for m in ms]
        self.assertIn('Shiny Hunter', names)


# ── I/O round-trip tests ─────────────────────────────────────────────────────

class _TmpDir:
    """Mixin: creates a temp dir and patches engine file-path globals for isolation."""
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp = Path(self._tmpdir.name)
        self._patches = [
            patch.object(engine, 'STATS_FILE',      tmp / 'buddy-stats.md'),
            patch.object(engine, 'BUDDY_FILE',       tmp / 'buddy-pokemon.md'),
            patch.object(engine, 'COLLECTION_FILE',  tmp / 'pokemon-collection.md'),
            patch.object(engine, 'STATE_FILE',       tmp / 'buddy-state.txt'),
            patch.object(engine, 'ARCHIVE_FILE',     tmp / 'buddy-log-archive.md'),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmpdir.cleanup()


class TestStatsRoundTrip(_TmpDir, unittest.TestCase):
    def test_write_then_read_preserves_all_fields(self):
        s = {
            'schema_version': 1,
            'streak': 7, 'last_xp_date': '2026-04-15', 'longest_streak': 14,
            'total_xp_ever': 850, 'bug_fixes': 5, 'features': 3, 'ships': 1,
            'caught_legendary': True, 'caught_mythical': False, 'caught_shiny': True,
            'milestones': {'first_catch', 'level_10', 'streak_7'},
        }
        engine.write_stats(s)
        got = engine.read_stats()

        self.assertEqual(got['streak'], 7)
        self.assertEqual(got['last_xp_date'], '2026-04-15')
        self.assertEqual(got['longest_streak'], 14)
        self.assertEqual(got['total_xp_ever'], 850)
        self.assertEqual(got['bug_fixes'], 5)
        self.assertEqual(got['features'], 3)
        self.assertEqual(got['ships'], 1)
        self.assertTrue(got['caught_legendary'])
        self.assertFalse(got['caught_mythical'])
        self.assertTrue(got['caught_shiny'])
        self.assertEqual(got['milestones'], {'first_catch', 'level_10', 'streak_7'})

    def test_missing_file_returns_defaults(self):
        s = engine.read_stats()
        self.assertEqual(s['streak'], 0)
        self.assertEqual(s['total_xp_ever'], 0)
        self.assertFalse(s['caught_legendary'])
        self.assertIsInstance(s['milestones'], set)

    def test_schema_version_written(self):
        engine.write_stats(engine.read_stats())
        text = engine.STATS_FILE.read_text(encoding='utf-8')
        self.assertIn('**schema_version**', text)

    def test_legacy_file_without_schema_version_reads_ok(self):
        """Files written before schema versioning should parse without error."""
        engine.STATS_FILE.write_text(
            '# Trainer Stats\n\n'
            '**streak**: 3\n'
            '**last_xp_date**: 2026-01-01\n'
            '**longest_streak**: 3\n'
            '**total_xp_ever**: 120\n'
            '**bug_fixes**: 2\n'
            '**features**: 0\n'
            '**ships**: 0\n'
            '**caught_legendary**: false\n'
            '**caught_mythical**: false\n'
            '**caught_shiny**: false\n\n'
            '## Milestones Awarded\n\n'
            '*(none yet)*\n',
            encoding='utf-8',
        )
        s = engine.read_stats()
        self.assertEqual(s['streak'], 3)
        self.assertEqual(s['schema_version'], engine.STATS_SCHEMA_VER)


class TestCollectionRoundTrip(_TmpDir, unittest.TestCase):
    def _sample_pokemon(self):
        return [
            {'name': 'Charmander', 'type': 'Fire', 'emoji': '🔥',
             'level': 5, 'xp': 250, 'caught': '2026-04-01', 'rarity': 'starter', 'shiny': False},
            {'name': 'Pikachu', 'type': 'Electric', 'emoji': '⚡',
             'level': 3, 'xp': 80, 'caught': '2026-04-10', 'rarity': 'uncommon', 'shiny': False},
        ]

    def test_write_then_read_preserves_party(self):
        pokemon = self._sample_pokemon()
        engine.write_collection('Charmander', pokemon)
        col = engine.read_collection()
        self.assertEqual(col['active'], 'Charmander')
        self.assertEqual(len(col['pokemon']), 2)
        names = [p['name'] for p in col['pokemon']]
        self.assertIn('Charmander', names)
        self.assertIn('Pikachu', names)

    def test_add_to_collection_appends_entry(self):
        engine.write_collection('Charmander', self._sample_pokemon())
        engine.add_to_collection('Mewtwo', 'Psychic', '🧬', 'legendary', False)
        col = engine.read_collection()
        names = [p['name'] for p in col['pokemon']]
        self.assertIn('Mewtwo', names)
        mewtwo = next(p for p in col['pokemon'] if p['name'] == 'Mewtwo')
        self.assertEqual(mewtwo['rarity'], 'legendary')
        self.assertEqual(mewtwo['level'], engine.RARITY_START_LEVEL['legendary'])

    def test_add_shiny_stores_shiny_rarity(self):
        engine.write_collection('Charmander', self._sample_pokemon())
        engine.add_to_collection('Mew', 'Psychic', '✨', 'mythical', True)
        col = engine.read_collection()
        mew = next(p for p in col['pokemon'] if p['name'] == 'Mew')
        self.assertEqual(mew['rarity'], 'mythical-shiny')
        self.assertTrue(mew['shiny'])

    def test_missing_file_returns_empty(self):
        col = engine.read_collection()
        self.assertIsNone(col['active'])
        self.assertEqual(col['pokemon'], [])

    def test_sync_active_updates_level_and_xp(self):
        engine.write_collection('Charmander', self._sample_pokemon())
        engine.sync_active_to_collection('Charmander', 10, 700)
        col = engine.read_collection()
        char = next(p for p in col['pokemon'] if p['name'] == 'Charmander')
        self.assertEqual(char['level'], 10)
        self.assertEqual(char['xp'], 700)


class TestRollCatch(_TmpDir, unittest.TestCase):
    def test_guaranteed_common_catch(self):
        """Patch random to always return 0 — all probabilities fire."""
        with patch('random.random', return_value=0.0), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')), \
             patch('random.choices', return_value=[('Pidgey', 'Normal', '🐦')]):
            result = engine.roll_catch(10, set())
        # With random=0, the 8% common catch fires and is_shiny=False (0 < SHINY_RATE is True)
        # is_shiny will be True since 0.0 < 0.005
        self.assertIsNotNone(result)
        tier, name, ptype, emoji, is_shiny = result
        self.assertEqual(tier, 'common')
        self.assertTrue(is_shiny)  # 0.0 < SHINY_RATE (0.005)

    def test_no_catch_when_probability_missed(self):
        """Patch random to always return 0.99 — nothing fires."""
        with patch('random.random', return_value=0.99):
            result = engine.roll_catch(10, set())
        self.assertIsNone(result)

    def test_already_owned_fallback_to_full_pool(self):
        """When all available pool members are owned, falls back to full pool."""
        common_names = {p[0] for p in engine.POKEMON_POOL['common']}
        with patch('random.random', return_value=0.0), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')), \
             patch('random.choices', return_value=[('Pidgey', 'Normal', '🐦')]):
            result = engine.roll_catch(10, common_names)
        # Should still return something (fallback to full pool)
        self.assertIsNotNone(result)

    def test_legendary_only_catchable_at_100xp(self):
        """Legendaries only appear in 100-XP catch rates."""
        rates_50  = dict(engine.CATCH_RATES.get(50, []))
        rates_100 = dict(engine.CATCH_RATES.get(100, []))
        self.assertNotIn('legendary', rates_50)
        self.assertIn('legendary', rates_100)

    def test_buddy_rarity_boost_increases_probability(self):
        """Legendary buddy should give a higher legendary catch multiplier."""
        boosts = engine.BUDDY_RARITY_BOOST.get('legendary', {})
        self.assertIn('legendary', boosts)
        self.assertGreater(boosts['legendary'], 1.0)


class TestReadBuddy(_TmpDir, unittest.TestCase):
    _SAMPLE_BUDDY = """\
# Buddy Pokemon: Charmander 🔥

**Name**: Charmander
**Type**: Fire 🔥
**Trainer**: Ash
**Specialty**: Frontend / JavaScript
**Level**: 5
**XP**: 250 / 400
**Stage**: Charmander 🔥

## Evolution Path

**Current Stage**: Charmander 🔥

```
Charmander Lv.1-15 → Charmeleon Lv.16-35 → Charizard Lv.36+
```

## Stats

| Stat | Value |
|---|---|
| HP | 39 |
| Attack | 52 |
| Defense | 43 |
| Special Atk | 60 |
| Special Def | 50 |
| Speed | 65 |

## Moves

| Move | Type | Unlocked At | Description |
|---|---|---|---|
| Scratch | Normal | Lv.1 | JS fundamentals |
| Ember | Fire | Lv.1 | First components/UI |

## Badges Earned

*No badges yet — the journey begins now!*

## Journey Log

| Date | Event | XP Gained |
|---|---|---|
| 2026-04-01 | Journey began! | — |

## Trainer Info

- **Trainer**: Ash
- **Role**: Frontend (Electric ⚡ domain)
- **Journey Started**: 2026-04-01
"""

    def setUp(self):
        super().setUp()
        engine.BUDDY_FILE.write_text(self._SAMPLE_BUDDY, encoding='utf-8')

    def test_reads_level_and_xp(self):
        _, _, level, xp, stage, name = engine.read_buddy()
        self.assertEqual(level, 5)
        self.assertEqual(xp, 250)

    def test_reads_stage_and_name(self):
        _, _, _, _, stage, name = engine.read_buddy()
        self.assertEqual(stage, 'Charmander')
        self.assertEqual(name, 'Charmander')

    def test_get_role_type_parses_electric(self):
        role_type = engine.get_role_type()
        self.assertEqual(role_type, 'Electric')

    def test_no_buddy_file_exits(self):
        engine.BUDDY_FILE.unlink()
        with self.assertRaises(SystemExit):
            engine.read_buddy()


if __name__ == '__main__':
    unittest.main()
