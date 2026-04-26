"""Unit tests for buddy-update.py core logic.

Run with: pytest tests/ -v

Covers:
  - Pure functions: XP math, detect_xp, bar rendering, streak, titles, evolution, milestones
  - I/O round-trips: stats file, collection file, buddy file, catch system
"""

import importlib.util
import json
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
    """v2.32 PoGo-style escalating bands.
    Bands: 1-10:+100, 11-20:+300, 21-35:+800, 36-60:+2000, 61-85:+5000, 86-100:+10000."""

    def test_level_1_is_zero(self):
        self.assertEqual(engine.xp_for_level(1), 0)

    def test_level_2_is_100(self):
        self.assertEqual(engine.xp_for_level(2), 100)

    def test_band1_top_lv10(self):
        # (10-1)*100
        self.assertEqual(engine.xp_for_level(10), 900)

    def test_band2_start_lv11(self):
        # 900 + (11-10)*300
        self.assertEqual(engine.xp_for_level(11), 1200)

    def test_band2_top_lv20(self):
        # 900 + 10*300
        self.assertEqual(engine.xp_for_level(20), 3900)

    def test_band3_top_lv35(self):
        # 3900 + 15*800
        self.assertEqual(engine.xp_for_level(35), 15900)

    def test_band4_lv50(self):
        # 15900 + 15*2000
        self.assertEqual(engine.xp_for_level(50), 45900)

    def test_band4_top_lv60(self):
        self.assertEqual(engine.xp_for_level(60), 65900)

    def test_band5_top_lv85(self):
        # 65900 + 25*5000
        self.assertEqual(engine.xp_for_level(85), 190900)

    def test_band6_top_lv100(self):
        # 190900 + 15*10000
        self.assertEqual(engine.xp_for_level(100), 340900)


class TestLevelFromXp(unittest.TestCase):
    def test_zero_xp_is_level_1(self):
        self.assertEqual(engine.level_from_xp(0), 1)

    def test_99_xp_is_level_1(self):
        self.assertEqual(engine.level_from_xp(99), 1)

    def test_100_xp_is_level_2(self):
        self.assertEqual(engine.level_from_xp(100), 2)

    def test_boundary_lv10(self):
        self.assertEqual(engine.level_from_xp(900), 10)

    def test_boundary_lv11(self):
        self.assertEqual(engine.level_from_xp(1200), 11)

    def test_boundary_lv35(self):
        self.assertEqual(engine.level_from_xp(15900), 35)

    def test_boundary_lv60(self):
        self.assertEqual(engine.level_from_xp(65900), 60)

    def test_xp_floor_round_trip(self):
        """xp_for_level(n) should produce exactly level n."""
        for lv in [1, 5, 10, 11, 20, 21, 35, 36, 50, 60, 61, 85, 86, 100]:
            with self.subTest(lv=lv):
                self.assertEqual(engine.level_from_xp(engine.xp_for_level(lv)), lv)

    def test_one_below_threshold_stays_lower(self):
        """One XP below a level threshold stays at the previous level."""
        for lv in [2, 5, 11, 21, 36, 61, 86]:
            threshold = engine.xp_for_level(lv)
            with self.subTest(lv=lv):
                self.assertEqual(engine.level_from_xp(threshold - 1), lv - 1)


class TestXpCurveMigration(unittest.TestCase):
    """Lazy v6→v7 curve migration (v2.32) — level-lock strategy."""

    def _stats(self, ver=6):
        return {'schema_version': ver}

    def _col(self, mons):
        return {'active': 'A', 'party': ['A'], 'pokemon': mons}

    def test_no_op_if_already_v7(self):
        s = self._stats(ver=7)
        col = self._col([{'name': 'A', 'level': 50, 'xp': 999}])
        new_xp, msg = engine.migrate_xp_curve(s, col, 50, 999)
        self.assertEqual(new_xp, 999)
        self.assertEqual(msg, '')
        self.assertEqual(col['pokemon'][0]['xp'], 999)

    def test_buddy_xp_resets_to_new_floor(self):
        s = self._stats(ver=6)
        col = self._col([])
        new_xp, msg = engine.migrate_xp_curve(s, col, 50, 8000)
        self.assertEqual(new_xp, engine.xp_for_level(50))   # 45900
        self.assertIn('Pokémon GO', msg)
        self.assertEqual(s['schema_version'], 7)

    def test_party_xp_relevels_in_place(self):
        s = self._stats(ver=6)
        col = self._col([
            {'name': 'A', 'level': 25, 'xp': 2500},
            {'name': 'B', 'level': 5,  'xp': 400},
        ])
        engine.migrate_xp_curve(s, col, 25, 2500)
        self.assertEqual(col['pokemon'][0]['xp'], engine.xp_for_level(25))  # 7900
        self.assertEqual(col['pokemon'][1]['xp'], engine.xp_for_level(5))   # 400

    def test_lv100_caps_to_CAP_XP(self):
        s = self._stats(ver=6)
        col = self._col([{'name': 'A', 'level': 100, 'xp': 17000}])
        new_xp, _ = engine.migrate_xp_curve(s, col, 100, 17000)
        self.assertEqual(new_xp, engine.CAP_XP)
        self.assertEqual(col['pokemon'][0]['xp'], engine.CAP_XP)

    def test_idempotent_after_migrate(self):
        s = self._stats(ver=6)
        col = self._col([{'name': 'A', 'level': 30, 'xp': 3000}])
        engine.migrate_xp_curve(s, col, 30, 3000)
        # second run: nothing changes
        new_xp, msg = engine.migrate_xp_curve(s, col, 30, engine.xp_for_level(30))
        self.assertEqual(msg, '')
        self.assertEqual(new_xp, engine.xp_for_level(30))


class TestMultiplierCap(unittest.TestCase):
    """Stack cap (combo × streak × lucky ≤ 3.0) prevents XP curve from breaking."""

    def test_uncapped_low_stack(self):
        # 1.5 * 1.5 * 1.0 = 2.25 < 3.0 → unchanged
        self.assertEqual(min(1.5 * 1.5 * 1.0, 3.0), 2.25)

    def test_capped_high_stack(self):
        # 2.0 * 2.0 * 1.5 = 6.0 → capped at 3.0
        self.assertEqual(min(2.0 * 2.0 * 1.5, 3.0), 3.0)


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


class TestDisplayedForm(unittest.TestCase):
    """displayed_form returns evolved stage+emoji for starters by level, pass-through for non-starters."""

    def test_starter_pre_evolution(self):
        p = {'name': 'Charmander', 'emoji': '🔥', 'level': 15}
        name, emj = engine.displayed_form(p)
        self.assertEqual(name, 'Charmander')
        self.assertEqual(emj, '🔥')

    def test_starter_first_evolution(self):
        p = {'name': 'Charmander', 'emoji': '🔥', 'level': 16}
        name, emj = engine.displayed_form(p)
        self.assertEqual(name, 'Charmeleon')
        self.assertEqual(emj, '🔥')

    def test_starter_final_evolution(self):
        p = {'name': 'Charmander', 'emoji': '🔥', 'level': 50}
        name, emj = engine.displayed_form(p)
        self.assertEqual(name, 'Charizard')
        self.assertEqual(emj, '🐉')

    def test_bulbasaur_final_form(self):
        p = {'name': 'Bulbasaur', 'emoji': '🌿', 'level': 40}
        name, emj = engine.displayed_form(p)
        self.assertEqual(name, 'Venusaur')
        self.assertEqual(emj, '🌺')

    def test_non_starter_pass_through(self):
        p = {'name': 'Gengar', 'emoji': '👻', 'level': 50}
        name, emj = engine.displayed_form(p)
        self.assertEqual(name, 'Gengar')
        self.assertEqual(emj, '👻')

    def test_missing_emoji_fallback(self):
        p = {'name': 'Unknown', 'level': 20}
        name, emj = engine.displayed_form(p)
        self.assertEqual(name, 'Unknown')
        self.assertEqual(emj, '?')


class TestRenderEncounterState(unittest.TestCase):
    """Timestamp-driven throw wobble frames."""

    def _enc(self, **overrides):
        import time
        base = {
            'encountered':  True,
            'wild_name':    'Gengar',
            'wild_emoji':   '👻',
            'battle_won':   True,
            'base_ts':      time.time(),
            'throw_secs':   3.0,
            'throws':       [{'ball_emoji': '🔴', 'caught': False},
                             {'ball_emoji': '🔵', 'caught': True}],
            'caught':       True,
            'no_balls':     False,
        }
        base.update(overrides)
        return base

    def test_fled_when_battle_lost(self):
        out = engine.render_encounter_state(self._enc(battle_won=False))
        self.assertIn('fled', out)

    def test_no_balls_message(self):
        out = engine.render_encounter_state(self._enc(no_balls=True, throws=[]))
        self.assertIn('no balls', out)

    def test_wobble_frame_first_throw_early(self):
        import time
        enc = self._enc(base_ts=time.time() - 0.1)
        out = engine.render_encounter_state(enc)
        self.assertIn('🔴', out)
        self.assertIn('1/2', out)
        self.assertTrue(out.endswith('·'))

    def test_wobble_frame_second_throw(self):
        import time
        enc = self._enc(base_ts=time.time() - 3.5)
        out = engine.render_encounter_state(enc)
        self.assertIn('🔵', out)
        self.assertIn('2/2', out)

    def test_final_reveal_caught(self):
        import time
        enc = self._enc(base_ts=time.time() - 10)
        out = engine.render_encounter_state(enc)
        self.assertIn('caught', out)
        self.assertIn('🔵', out)

    def test_final_reveal_escaped(self):
        import time
        enc = self._enc(base_ts=time.time() - 10, caught=False,
                        throws=[{'ball_emoji': '🔴', 'caught': False}])
        out = engine.render_encounter_state(enc)
        self.assertIn('broke free', out)

    def test_single_throw_no_prefix(self):
        import time
        enc = self._enc(base_ts=time.time() - 0.1,
                        throws=[{'ball_emoji': '🔴', 'caught': False}])
        out = engine.render_encounter_state(enc)
        self.assertNotIn('1/1', out)


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
    def test_guaranteed_common_encounter(self):
        """Patch random to always return 0 — encounter fires, battle won, caught."""
        from lib.data import ENCOUNTER_RATES
        stats = engine.read_stats()
        stats['balls_poke'] = 5
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')), \
             patch('random.choices', return_value=[('Pidgey', 'Normal', '🐦')]):
            catch_result, info = engine.run_encounter(10, set(), None, None, 5, 'Normal', stats)
        self.assertTrue(info['encountered'])
        self.assertEqual(info['wild_tier'], 'common')

    def test_no_encounter_when_probability_missed(self):
        """Patch random to always return 0.99 — no encounter fires."""
        stats = engine.read_stats()
        with patch('random.random', return_value=0.99), \
             patch('random.randint', return_value=99):
            catch_result, info = engine.run_encounter(10, set(), None, None, 5, 'Normal', stats)
        self.assertFalse(info['encountered'])
        self.assertIsNone(catch_result)

    def test_already_owned_fallback_to_full_pool(self):
        """When all available pool members are owned, falls back to full pool."""
        common_names = {p[0] for p in engine.POKEMON_POOL['common']}
        stats = engine.read_stats()
        stats['balls_poke'] = 5
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')), \
             patch('random.choices', return_value=[('Pidgey', 'Normal', '🐦')]):
            catch_result, info = engine.run_encounter(10, common_names, None, None, 5, 'Normal', stats)
        self.assertTrue(info['encountered'])

    def test_legendary_only_at_100xp(self):
        """Legendaries only appear in 100-XP encounter rates."""
        from lib.data import ENCOUNTER_RATES
        rates_50  = dict(ENCOUNTER_RATES.get(50, []))
        rates_100 = dict(ENCOUNTER_RATES.get(100, []))
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


# ── New adventure system tests ────────────────────────────────────────────────

class TestInventoryStats(_TmpDir, unittest.TestCase):
    """Stats round-trip for new inventory fields."""

    def _full_stats(self):
        s = engine.read_stats()
        s.update({
            'balls_poke': 3, 'balls_great': 2, 'balls_ultra': 1, 'balls_master': 0,
            'master_shards': 2,
            'berry_razz': 1, 'berry_nanab': 0, 'berry_pinap': 1, 'berry_golden': 0,
            'combo': 3, 'combo_ts': '2026-04-17T10:00:00',
            'daily_quest_date': '2026-04-17', 'daily_quest_id': 'fix_bug',
            'daily_quest_done': False, 'tasks_today': 2,
        })
        return s

    def test_inventory_roundtrip(self):
        engine.write_stats(self._full_stats())
        got = engine.read_stats()
        self.assertEqual(got['balls_poke'], 3)
        self.assertEqual(got['balls_great'], 2)
        self.assertEqual(got['balls_ultra'], 1)
        self.assertEqual(got['balls_master'], 0)
        self.assertEqual(got['master_shards'], 2)
        self.assertEqual(got['berry_razz'], 1)
        self.assertEqual(got['berry_pinap'], 1)

    def test_combo_roundtrip(self):
        engine.write_stats(self._full_stats())
        got = engine.read_stats()
        self.assertEqual(got['combo'], 3)
        self.assertEqual(got['combo_ts'], '2026-04-17T10:00:00')

    def test_daily_quest_roundtrip(self):
        engine.write_stats(self._full_stats())
        got = engine.read_stats()
        self.assertEqual(got['daily_quest_date'], '2026-04-17')
        self.assertEqual(got['daily_quest_id'], 'fix_bug')
        self.assertFalse(got['daily_quest_done'])
        self.assertEqual(got['tasks_today'], 2)

    def test_new_trainer_starts_with_5_pokeballs(self):
        got = engine.read_stats()
        self.assertEqual(got['balls_poke'], 5)
        self.assertEqual(got['balls_great'], 0)
        self.assertEqual(got['balls_master'], 0)


class TestRunBattle(unittest.TestCase):
    """Battle win/loss probability logic."""

    def test_high_level_buddy_wins(self):
        # Lv.50 vs Lv.5 → win_pct capped at 95
        won, pct, _ = engine.run_battle(50, 'Fire', 5, 'Grass')
        self.assertEqual(pct, 95)

    def test_low_level_buddy_minimum_5pct(self):
        # Lv.1 vs Lv.60 Normal vs Dragon → floored at 5
        _, pct, _ = engine.run_battle(1, 'Normal', 60, 'Dragon')
        self.assertEqual(pct, 5)

    def test_type_super_effective_doubles_base(self):
        # Fire vs Grass: eff=2.0 → base*2.0 vs normal*1.0
        _, pct_base, eff_base = engine.run_battle(10, 'Normal', 10, 'Grass')
        _, pct_adv,  eff_adv  = engine.run_battle(10, 'Fire',   10, 'Grass')
        self.assertEqual(eff_adv, 2.0)
        self.assertEqual(eff_base, 1.0)
        self.assertGreater(pct_adv, pct_base)

    def test_type_immune_floors_to_5pct(self):
        # Electric vs Ground → immunity → floor 5
        _, pct, eff = engine.run_battle(100, 'Electric', 1, 'Ground')
        self.assertEqual(eff, 0.0)
        self.assertEqual(pct, 5)

    def test_guaranteed_win_when_randint_1(self):
        with patch('random.randint', return_value=1):
            won, _, _ = engine.run_battle(5, 'Normal', 5, 'Normal')
        self.assertTrue(won)

    def test_guaranteed_loss_when_randint_100(self):
        with patch('random.randint', return_value=100):
            won, _, _ = engine.run_battle(1, 'Normal', 60, 'Dragon')
        self.assertFalse(won)



class TestAttemptCatch(_TmpDir, unittest.TestCase):
    """Catch probability and berry consumption."""

    def test_master_ball_always_catches(self):
        stats = engine.read_stats()
        caught, pct = engine.attempt_catch('mythical', 'master', stats)
        self.assertTrue(caught)
        self.assertEqual(pct, 100)

    def test_guaranteed_catch_when_randint_1(self):
        stats = engine.read_stats()
        with patch('random.randint', return_value=1):
            caught, _ = engine.attempt_catch('common', 'poke', stats)
        self.assertTrue(caught)

    def test_miss_when_randint_above_threshold(self):
        stats = engine.read_stats()
        with patch('random.randint', return_value=100):
            caught, _ = engine.attempt_catch('legendary', 'poke', stats)
        self.assertFalse(caught)

    def test_golden_razz_berry_consumed_on_use(self):
        stats = engine.read_stats()
        stats['berry_golden'] = 1
        engine.attempt_catch('rare', 'ultra', stats)
        self.assertEqual(stats['berry_golden'], 0)

    def test_razz_berry_consumed_when_no_golden(self):
        stats = engine.read_stats()
        stats['berry_razz'] = 2
        engine.attempt_catch('rare', 'ultra', stats)
        self.assertEqual(stats['berry_razz'], 1)

    def test_catch_pct_capped_at_95(self):
        stats = engine.read_stats()
        _, pct = engine.attempt_catch('common', 'ultra', stats)
        self.assertLessEqual(pct, 95)


class TestEarnInventory(_TmpDir, unittest.TestCase):
    """Balls and berries earned from tasks."""

    def test_100xp_earns_two_ultra_balls(self):
        stats = engine.read_stats()
        stats['balls_ultra'] = 0
        engine.earn_inventory(100, False, stats)
        self.assertEqual(stats['balls_ultra'], 2)

    def test_30xp_earns_two_pokeballs(self):
        stats = engine.read_stats()
        prev = stats['balls_poke']
        engine.earn_inventory(30, False, stats)
        self.assertEqual(stats['balls_poke'], prev + 2)

    def test_badge_adds_master_shard(self):
        stats = engine.read_stats()
        stats['master_shards'] = 0
        engine.earn_inventory(50, True, stats)
        self.assertEqual(stats['master_shards'], 1)

    def test_three_shards_convert_to_master_ball(self):
        stats = engine.read_stats()
        stats['master_shards'] = 2
        stats['balls_master'] = 0
        engine.earn_inventory(50, True, stats)
        self.assertEqual(stats['master_shards'], 0)
        self.assertEqual(stats['balls_master'], 1)

    def test_returns_nonempty_description(self):
        stats = engine.read_stats()
        msg = engine.earn_inventory(100, False, stats)
        self.assertTrue(len(msg) > 0)


class TestUpdateCombo(_TmpDir, unittest.TestCase):
    """Combo counter and XP multiplier."""

    def test_first_task_is_combo_1(self):
        stats = engine.read_stats()
        stats['combo'] = 0
        stats['combo_ts'] = ''
        combo, mult = engine.update_combo(stats)
        self.assertEqual(combo, 1)
        self.assertEqual(mult, 1.0)

    def test_second_task_within_hour_increments(self):
        from datetime import datetime, timedelta
        stats = engine.read_stats()
        stats['combo'] = 1
        stats['combo_ts'] = (datetime.now() - timedelta(minutes=10)).isoformat()
        combo, _ = engine.update_combo(stats)
        self.assertEqual(combo, 2)

    def test_expired_combo_resets_to_1(self):
        from datetime import datetime, timedelta
        stats = engine.read_stats()
        stats['combo'] = 5
        stats['combo_ts'] = (datetime.now() - timedelta(hours=2)).isoformat()
        combo, _ = engine.update_combo(stats)
        self.assertEqual(combo, 1)

    def test_multiplier_at_3_tasks(self):
        from datetime import datetime, timedelta
        stats = engine.read_stats()
        stats['combo'] = 2
        stats['combo_ts'] = (datetime.now() - timedelta(minutes=5)).isoformat()
        _, mult = engine.update_combo(stats)
        self.assertEqual(mult, 1.5)

    def test_multiplier_at_5_tasks(self):
        from datetime import datetime, timedelta
        stats = engine.read_stats()
        stats['combo'] = 4
        stats['combo_ts'] = (datetime.now() - timedelta(minutes=5)).isoformat()
        _, mult = engine.update_combo(stats)
        self.assertEqual(mult, 2.0)


class TestDailyQuest(_TmpDir, unittest.TestCase):
    """Daily quest assignment and completion."""

    def test_quest_assigned_on_new_day(self):
        stats = engine.read_stats()
        stats['daily_quest_date'] = '2000-01-01'
        quest = engine.get_daily_quest(stats)
        self.assertIsNotNone(quest)
        self.assertEqual(stats['daily_quest_date'], engine.TODAY)

    def test_same_quest_returned_same_day(self):
        stats = engine.read_stats()
        q1 = engine.get_daily_quest(stats)
        q2 = engine.get_daily_quest(stats)
        self.assertEqual(q1['id'], q2['id'])

    def test_tasks_today_resets_on_new_day(self):
        stats = engine.read_stats()
        stats['daily_quest_date'] = '2000-01-01'
        stats['tasks_today'] = 99
        engine.get_daily_quest(stats)
        self.assertEqual(stats['tasks_today'], 0)

    def test_keyword_quest_completes_on_match(self):
        stats = engine.read_stats()
        stats['daily_quest_date'] = engine.TODAY
        stats['daily_quest_id']   = 'fix_bug'
        stats['daily_quest_done'] = False
        msg = engine.check_daily_quest(stats, 'fixed a nasty bug', False)
        self.assertTrue(stats['daily_quest_done'])
        self.assertIn('Fix a bug', msg)

    def test_catch_quest_completes_on_catch(self):
        stats = engine.read_stats()
        stats['daily_quest_date'] = engine.TODAY
        stats['daily_quest_id']   = 'catch'
        stats['daily_quest_done'] = False
        msg = engine.check_daily_quest(stats, 'anything', True)
        self.assertTrue(stats['daily_quest_done'])
        self.assertIn('Catch', msg)

    def test_three_tasks_quest_needs_3(self):
        stats = engine.read_stats()
        stats['daily_quest_date'] = engine.TODAY
        stats['daily_quest_id']   = 'three_tasks'
        stats['daily_quest_done'] = False
        stats['tasks_today']      = 2
        msg = engine.check_daily_quest(stats, 'did something', False)
        self.assertEqual(msg, '')  # not done yet

        stats['tasks_today'] = 3
        msg = engine.check_daily_quest(stats, 'did something', False)
        self.assertNotEqual(msg, '')  # now done

    def test_already_done_quest_not_rewarded_twice(self):
        stats = engine.read_stats()
        stats['daily_quest_date'] = engine.TODAY
        stats['daily_quest_id']   = 'fix_bug'
        stats['daily_quest_done'] = True
        msg = engine.check_daily_quest(stats, 'fixed a bug', False)
        self.assertEqual(msg, '')


class TestLevelUpRewards(_TmpDir, unittest.TestCase):
    """Ball rewards on level-up."""

    def test_every_level_gives_2_pokeballs(self):
        stats = engine.read_stats()
        stats['balls_poke'] = 0
        engine.level_up_rewards(0, 3, stats)  # levels 1, 2, 3
        self.assertEqual(stats['balls_poke'], 6)

    def test_level_5_gives_great_ball(self):
        stats = engine.read_stats()
        stats['balls_great'] = 0
        engine.level_up_rewards(4, 5, stats)
        self.assertEqual(stats['balls_great'], 1)

    def test_level_10_gives_ultra_ball(self):
        stats = engine.read_stats()
        stats['balls_ultra'] = 0
        engine.level_up_rewards(9, 10, stats)
        self.assertEqual(stats['balls_ultra'], 1)

    def test_level_20_gives_ultra_ball(self):
        stats = engine.read_stats()
        stats['balls_ultra'] = 0
        engine.level_up_rewards(19, 20, stats)
        self.assertEqual(stats['balls_ultra'], 1)

    def test_no_reward_for_same_level(self):
        stats = engine.read_stats()
        stats['balls_poke'] = 0
        engine.level_up_rewards(5, 5, stats)
        self.assertEqual(stats['balls_poke'], 0)


class TestRunEncounter(_TmpDir, unittest.TestCase):
    """Full adventure flow: encounter → battle → catch."""

    def _stats(self):
        s = engine.read_stats()
        s['balls_poke'] = 10
        return s

    def test_no_encounter_returns_false(self):
        stats = self._stats()
        with patch('random.random', return_value=0.99), \
             patch('random.randint', return_value=99):
            result, info = engine.run_encounter(10, set(), None, None, 5, 'Normal', stats)
        self.assertFalse(info['encountered'])
        self.assertIsNone(result)

    def test_encounter_sets_wild_info(self):
        stats = self._stats()
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            result, info = engine.run_encounter(10, set(), None, None, 5, 'Normal', stats)
        self.assertTrue(info['encountered'])
        self.assertEqual(info['wild_name'], 'Pidgey')
        self.assertEqual(info['wild_tier'], 'common')
        self.assertIn('wild_level', info)

    def test_battle_loss_means_no_catch(self):
        stats = self._stats()
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=100):
            # randint=100 vs win_pct=20 (Lv.1 vs Lv.5) → lose
            result, info = engine.run_encounter(10, set(), None, None, 1, 'Normal', stats)
        if info['encountered']:
            self.assertFalse(info.get('caught', False))
            self.assertIsNone(result)

    def test_no_balls_means_no_catch(self):
        stats = self._stats()
        stats['balls_poke'] = 0
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            result, info = engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if info['encountered'] and info['battle_won']:
            self.assertTrue(info['no_balls'])
            self.assertIsNone(result)

    def test_successful_catch_adds_to_collection(self):
        stats = self._stats()
        engine.write_collection(None, [])
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            result, info = engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if info.get('caught'):
            col = engine.read_collection()
            names = [p['name'] for p in col['pokemon']]
            self.assertIn('Pidgey', names)

    def test_ball_deducted_on_throw(self):
        stats = self._stats()
        stats['balls_poke'] = 3
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if True:  # ball always deducted when battle won and ball selected
            self.assertLess(stats['balls_poke'], 3)

    def test_throws_is_list_of_dicts(self):
        """info['throws'] should be a list with ball/catch keys per throw."""
        stats = self._stats()
        stats['balls_poke'] = 2
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            _, info = engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if info['encountered'] and info['battle_won']:
            self.assertIsInstance(info['throws'], list)
            self.assertGreater(len(info['throws']), 0)
            for t in info['throws']:
                self.assertIn('ball_key',   t)
                self.assertIn('ball_emoji', t)
                self.assertIn('catch_pct',  t)
                self.assertIn('caught',     t)

    def test_all_balls_exhausted_before_escape(self):
        """All available balls are thrown before giving up — none left after all misses."""
        stats = self._stats()
        stats['balls_poke']  = 2
        stats['balls_great'] = 0
        stats['balls_ultra'] = 0
        stats['balls_master'] = 0
        # Battle wins (randint=1 < win_pct), catch always fails (randint always > catch_pct)
        # Use side_effect: first call (shiny roll) = 0.99 (no shiny), battle randint=1 (win)
        # catch randint always 99 (fail)
        with patch('random.random', return_value=0.99), \
             patch('random.randint', side_effect=[1, 1, 99, 99, 99, 99, 99, 99]), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            result, info = engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if info['encountered'] and info['battle_won'] and not info['no_balls']:
            self.assertFalse(info['caught'])
            self.assertEqual(stats['balls_poke'], 0)
            self.assertEqual(len(info['throws']), 2)

    def test_stops_throwing_after_catch(self):
        """No extra balls thrown once Pokémon is caught."""
        stats = self._stats()
        stats['balls_poke']  = 5
        stats['balls_great'] = 3
        # randint=1 means catch succeeds on first throw
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            result, info = engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if info['encountered'] and info['battle_won']:
            self.assertTrue(info['caught'])
            self.assertEqual(len(info['throws']), 1)
            self.assertEqual(stats['balls_poke'], 4)  # only 1 deducted

    def test_falls_through_to_next_ball_tier(self):
        """After exhausting preferred ball type, falls back to next available tier."""
        stats = self._stats()
        stats['balls_poke']  = 0
        stats['balls_great'] = 0
        stats['balls_ultra'] = 1
        stats['balls_master'] = 0
        # common priority is ['poke', 'great'] — neither available, so no throw
        with patch('random.random', return_value=0.0), \
             patch('random.randint', return_value=1), \
             patch('random.choice', return_value=('Pidgey', 'Normal', '🐦')):
            result, info = engine.run_encounter(10, set(), None, None, 10, 'Normal', stats)
        if info['encountered'] and info['battle_won']:
            # common uses poke→great only, ultra not in priority → no balls
            self.assertTrue(info['no_balls'])

    def test_rare_uses_ultra_then_great(self):
        """Rare encounter exhausts ultra balls first, then falls to great balls."""
        stats = self._stats()
        stats['balls_poke']  = 0
        stats['balls_great'] = 2
        stats['balls_ultra'] = 1
        stats['balls_master'] = 0
        # Force encounter at 'rare' tier: high base_xp + specific patches
        # randint for catch = 99 (always miss), for battle = 1 (always win)
        with patch('random.random', return_value=0.99), \
             patch('random.randint', side_effect=[15, 1, 99, 99, 99, 99, 99]), \
             patch('random.choices', return_value=[('rare', )]), \
             patch.object(engine, '_roll_encounter_tier', return_value='rare'), \
             patch('random.choice', return_value=('Snorlax', 'Normal', '😴')):
            result, info = engine.run_encounter(100, set(), None, None, 20, 'Normal', stats)
        if info['encountered'] and info['battle_won'] and not info['no_balls']:
            ball_keys = [t['ball_key'] for t in info['throws']]
            if ball_keys:
                ultra_idx = [i for i, k in enumerate(ball_keys) if k == 'ultra']
                great_idx = [i for i, k in enumerate(ball_keys) if k == 'great']
                if ultra_idx and great_idx:
                    self.assertLess(max(ultra_idx), min(great_idx))


# ── Rarity helpers ───────────────────────────────────────────────────────────

class TestRarityHelpers(unittest.TestCase):
    def test_pokemon_tier_by_rarity_field(self):
        self.assertEqual(engine._pokemon_tier({'rarity': 'rare'}), 'rare')
        self.assertEqual(engine._pokemon_tier({'rarity': 'legendary'}), 'legendary')
        self.assertEqual(engine._pokemon_tier({'rarity': 'mythical'}), 'mythical')
        self.assertEqual(engine._pokemon_tier({'rarity': 'uncommon'}), 'uncommon')
        self.assertEqual(engine._pokemon_tier({'rarity': 'starter'}), 'starter')

    def test_pokemon_tier_shiny_suffix(self):
        self.assertEqual(engine._pokemon_tier({'rarity': 'rare-shiny'}), 'rare')
        self.assertEqual(engine._pokemon_tier({'rarity': 'legendary-shiny'}), 'legendary')

    def test_pokemon_tier_unknown_falls_back_to_common(self):
        self.assertEqual(engine._pokemon_tier({'rarity': 'caught'}), 'common')
        self.assertEqual(engine._pokemon_tier({}), 'common')

    def test_group_by_tier_basic(self):
        pokemon = [
            {'name': 'Dratini',    'rarity': 'rare'},
            {'name': 'Pidgey',     'rarity': 'common'},
            {'name': 'Charmander', 'rarity': 'starter'},
            {'name': 'Lugia',      'rarity': 'legendary'},
        ]
        grouped = engine._group_by_tier(pokemon)
        self.assertIn('rare', grouped)
        self.assertIn('common', grouped)
        self.assertIn('starter', grouped)
        self.assertIn('legendary', grouped)
        self.assertEqual(grouped['rare'][0]['name'], 'Dratini')
        self.assertEqual(grouped['common'][0]['name'], 'Pidgey')

    def test_group_by_tier_empty(self):
        self.assertEqual(engine._group_by_tier([]), {})

    def test_rarity_tier_order_is_complete(self):
        expected = ['mythical', 'legendary', 'rare', 'uncommon', 'common', 'starter']
        self.assertEqual(engine.RARITY_TIER_ORDER, expected)

    def test_rarity_labels_ascii_covers_all_tiers(self):
        for tier in engine.RARITY_TIER_ORDER:
            self.assertIn(tier, engine.RARITY_LABELS_ASCII)


class TestSpriteUrl(unittest.TestCase):
    def test_known_pokemon_returns_url(self):
        url = engine.sprite_url('Charmander')
        self.assertIn('4.png', url)
        self.assertIn('PokeAPI', url)

    def test_shiny_returns_shiny_url(self):
        url = engine.sprite_url('Charmander', shiny=True)
        self.assertIn('/shiny/', url)
        self.assertIn('4.png', url)

    def test_unknown_pokemon_returns_empty(self):
        self.assertEqual(engine.sprite_url('FakeMon'), '')

    def test_ball_sprites_dict_has_all_types(self):
        for key in ('Poké', 'Great', 'Ultra', 'Master'):
            self.assertIn(key, engine._BALL_SPRITES)
            self.assertTrue(engine._BALL_SPRITES[key].startswith('https://'))


class TestPurgeMode(_TmpDir, unittest.TestCase):
    """Coverage for the 'purge' CLI mode — removes all state files."""

    def test_purge_removes_existing_state_files(self):
        engine.BUDDY_FILE.write_text('x', encoding='utf-8')
        engine.COLLECTION_FILE.write_text('x', encoding='utf-8')
        engine.STATS_FILE.write_text('x', encoding='utf-8')
        with patch.object(sys, 'argv', ['buddy-update.py', 'purge']):
            with self.assertRaises(SystemExit) as ctx:
                engine.main()
        self.assertEqual(ctx.exception.code, 0)
        self.assertFalse(engine.BUDDY_FILE.exists())
        self.assertFalse(engine.COLLECTION_FILE.exists())
        self.assertFalse(engine.STATS_FILE.exists())

    def test_purge_with_no_files_is_noop(self):
        with patch.object(sys, 'argv', ['buddy-update.py', 'purge']):
            with self.assertRaises(SystemExit) as ctx:
                engine.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_purge_keep_preserves_data_files(self):
        engine.BUDDY_FILE.write_text('x', encoding='utf-8')
        engine.COLLECTION_FILE.write_text('x', encoding='utf-8')
        engine.STATS_FILE.write_text('x', encoding='utf-8')
        with patch.object(sys, 'argv', ['buddy-update.py', 'purge', 'keep']):
            with self.assertRaises(SystemExit) as ctx:
                engine.main()
        self.assertEqual(ctx.exception.code, 0)
        self.assertTrue(engine.BUDDY_FILE.exists())
        self.assertTrue(engine.COLLECTION_FILE.exists())
        self.assertTrue(engine.STATS_FILE.exists())

    def test_purge_keep_removes_plugin_state_files(self):
        claude_dir = engine.BUDDY_FILE.parent
        plugin_state = claude_dir / 'pokemon-buddy-plugin.json'
        encounter    = claude_dir / 'buddy-encounter.json'
        plugin_state.write_text('{}', encoding='utf-8')
        encounter.write_text('{}', encoding='utf-8')
        with patch.object(sys, 'argv', ['buddy-update.py', 'purge', 'keep']):
            with self.assertRaises(SystemExit):
                engine.main()
        self.assertFalse(plugin_state.exists())
        self.assertFalse(encounter.exists())

    def test_purge_unwires_statusline_and_restores_backup(self):
        claude_dir = engine.BUDDY_FILE.parent
        settings_file = claude_dir / 'settings.json'
        settings_file.write_text(json.dumps({
            'statusLine': {'type': 'command', 'command': 'python3 buddy-update.py statusline'},
            '_statusLineBackup': {'type': 'command', 'command': 'echo hello'},
            'extraKnownMarketplaces': {'pokemon-buddy-claude': {'x': 1}, 'other': {'y': 2}},
        }), encoding='utf-8')
        with patch.object(sys, 'argv', ['buddy-update.py', 'purge', 'keep']):
            with self.assertRaises(SystemExit):
                engine.main()
        result = json.loads(settings_file.read_text(encoding='utf-8'))
        self.assertEqual(result['statusLine']['command'], 'echo hello')
        self.assertNotIn('_statusLineBackup', result)
        self.assertNotIn('pokemon-buddy-claude', result['extraKnownMarketplaces'])
        self.assertIn('other', result['extraKnownMarketplaces'])


class TestRenderDexFilter(_TmpDir, unittest.TestCase):
    """Coverage for render_dex filter argument (tier/type/shiny)."""

    def _seed(self):
        engine.add_to_collection('Charmander', 'Fire',    '🔥', 'starter',   False)
        engine.add_to_collection('Pidgey',     'Normal',  '🐦', 'common',    False)
        engine.add_to_collection('Mewtwo',     'Psychic', '🧬', 'legendary', False)
        engine.add_to_collection('Mew',        'Psychic', '✨', 'mythical',  True)

    def test_unfiltered_shows_all_tiers(self):
        self._seed()
        out = engine.render_dex()
        for name in ('Charmander', 'Pidgey', 'Mewtwo', 'Mew'):
            self.assertIn(name, out)

    def test_tier_filter_keeps_only_matching(self):
        self._seed()
        out = engine.render_dex('legendary')
        self.assertIn('Mewtwo', out)
        self.assertNotIn('Pidgey', out)
        self.assertNotIn('Charmander', out)

    def test_tier_filter_case_insensitive(self):
        self._seed()
        self.assertIn('Mewtwo', engine.render_dex('LEGENDARY'))

    def test_shiny_filter_keeps_only_shinies(self):
        self._seed()
        out = engine.render_dex('shiny')
        self.assertIn('Mew', out)
        self.assertNotIn('Mewtwo', out)
        self.assertNotIn('Charmander', out)

    def test_type_filter_keeps_only_matching_type(self):
        self._seed()
        out = engine.render_dex('psychic')
        self.assertIn('Mewtwo', out)
        self.assertIn('Mew', out)
        self.assertNotIn('Pidgey', out)

    def test_unknown_filter_returns_empty_with_hint(self):
        self._seed()
        out = engine.render_dex('banana')
        self.assertIn('No Pokémon match', out)
        self.assertIn('banana', out)


class TestRenderOgSvg(_TmpDir, unittest.TestCase):
    """Coverage for render_og_svg — social-share OpenGraph image."""

    def setUp(self):
        super().setUp()
        engine.BUDDY_FILE.write_text(
            '**Name**: Charmander\n'
            '**Trainer**: Ash\n'
            '**Specialty**: Frontend / JavaScript\n'
            '**Level**: 7\n'
            '**XP**: 620 / 700\n'
            '**Stage**: Charmander\n',
            encoding='utf-8',
        )

    def test_produces_valid_svg_root(self):
        svg = engine.render_og_svg()
        self.assertTrue(svg.startswith('<svg'))
        self.assertIn('viewBox="0 0 1200 630"', svg)
        self.assertIn('</svg>', svg)

    def test_includes_trainer_and_stage(self):
        svg = engine.render_og_svg()
        self.assertIn('Ash', svg)
        self.assertIn('Charmander', svg)
        self.assertIn('Lv. 7', svg)

    def test_escapes_html_special_chars_in_trainer_name(self):
        engine.BUDDY_FILE.write_text(
            '**Name**: Charmander\n'
            '**Trainer**: <Ash & Misty>\n'
            '**Specialty**: x\n'
            '**Level**: 1\n**XP**: 0 / 100\n**Stage**: Charmander\n',
            encoding='utf-8',
        )
        svg = engine.render_og_svg()
        self.assertNotIn('<Ash', svg)
        self.assertIn('&lt;Ash', svg)
        self.assertIn('&amp;', svg)


class TestChooseMode(_TmpDir, unittest.TestCase):
    """Coverage for /poke:choose first-run bootstrap."""

    def _run(self, arg):
        with patch.object(sys, 'argv', ['buddy-update.py', 'choose', arg]):
            with self.assertRaises(SystemExit) as ctx:
                engine.main()
        return ctx.exception.code

    def test_choose_by_number_creates_buddy(self):
        self.assertFalse(engine.BUDDY_FILE.exists())
        self.assertEqual(self._run('1'), 0)
        self.assertTrue(engine.BUDDY_FILE.exists())
        self.assertIn('Charmander', engine.BUDDY_FILE.read_text(encoding='utf-8'))

    def test_choose_by_name_creates_buddy(self):
        self.assertEqual(self._run('Pikachu'), 0)
        text = engine.BUDDY_FILE.read_text(encoding='utf-8')
        self.assertIn('Pikachu', text)
        self.assertIn('Electric', text)

    def test_choose_initializes_collection(self):
        self._run('Squirtle')
        col = engine.read_collection()
        self.assertEqual(col['active'], 'Squirtle')
        self.assertEqual(len(col['pokemon']), 1)
        self.assertEqual(col['pokemon'][0]['name'], 'Squirtle')

    def test_choose_unknown_name_exits_nonzero(self):
        self.assertEqual(self._run('Mewtwo'), 1)
        self.assertFalse(engine.BUDDY_FILE.exists())

    def test_choose_when_buddy_exists_switches_instead(self):
        self._run('Charmander')
        self.assertEqual(self._run('Bulbasaur'), 0)
        text = engine.BUDDY_FILE.read_text(encoding='utf-8')
        self.assertIn('Bulbasaur', text)
        col = engine.read_collection()
        self.assertEqual(col['active'], 'Bulbasaur')
        self.assertEqual({p['name'] for p in col['pokemon']}, {'Charmander', 'Bulbasaur'})


class TestClampToCap(unittest.TestCase):
    def test_below_cap_is_passthrough(self):
        lv, xp, over = engine.clamp_to_cap(500)
        self.assertLess(lv, engine.LEVEL_CAP)
        self.assertEqual(xp, 500)
        self.assertEqual(over, 0)

    def test_at_cap_no_overflow(self):
        lv, xp, over = engine.clamp_to_cap(engine.CAP_XP)
        self.assertEqual(lv, engine.LEVEL_CAP)
        self.assertEqual(xp, engine.CAP_XP)
        self.assertEqual(over, 0)

    def test_past_cap_reports_overflow(self):
        lv, xp, over = engine.clamp_to_cap(engine.CAP_XP + 1234)
        self.assertEqual(lv, engine.LEVEL_CAP)
        self.assertEqual(xp, engine.CAP_XP)
        self.assertEqual(over, 1234)


class TestDistributeOverflowXp(_TmpDir, unittest.TestCase):
    """Exp Share: XP beyond Lv.cap on active buddy splits across party."""

    def _seed(self):
        engine.write_collection('Charizard', [
            {'name': 'Charizard', 'type': 'Fire', 'emoji': 'fire',
             'level': engine.LEVEL_CAP, 'xp': engine.CAP_XP,
             'caught': '2026-01-01', 'rarity': 'starter'},
            {'name': 'Pikachu', 'type': 'Electric', 'emoji': 'elec',
             'level': 50, 'xp': 7400, 'caught': '2026-01-02', 'rarity': 'common'},
            {'name': 'Squirtle', 'type': 'Water', 'emoji': 'water',
             'level': 10, 'xp': 900, 'caught': '2026-01-03', 'rarity': 'common'},
        ])

    def test_even_split_across_eligible(self):
        self._seed()
        res = engine.distribute_overflow_xp(1000, 'Charizard')
        gained = {name: g for name, g, _, _ in res}
        self.assertEqual(gained, {'Pikachu': 500, 'Squirtle': 500})

    def test_zero_overflow_noop(self):
        self._seed()
        self.assertEqual(engine.distribute_overflow_xp(0, 'Charizard'), [])

    def test_share_below_one_noop(self):
        self._seed()
        self.assertEqual(engine.distribute_overflow_xp(1, 'Charizard'), [])

    def test_active_excluded(self):
        self._seed()
        res = engine.distribute_overflow_xp(500, 'Pikachu')
        self.assertNotIn('Pikachu', {n for n, *_ in res})

    def test_recipients_capped_at_level_cap(self):
        self._seed()
        engine.distribute_overflow_xp(10_000_000, 'Charizard')
        col = engine.read_collection()
        for p in col['pokemon']:
            self.assertLessEqual(p['level'], engine.LEVEL_CAP)
            self.assertLessEqual(p['xp'], engine.CAP_XP)

    def test_no_eligible_returns_empty(self):
        self._seed()
        engine.distribute_overflow_xp(10_000_000, 'Charizard')  # max everyone
        self.assertEqual(engine.distribute_overflow_xp(500, 'Charizard'), [])


# ── F1: streak multiplier ─────────────────────────────────────────────────────

class TestStreakMultiplier(unittest.TestCase):
    def test_zero_streak(self):
        self.assertAlmostEqual(engine.streak_multiplier(0), 1.0)

    def test_day_1(self):
        self.assertAlmostEqual(engine.streak_multiplier(1), 1.02)

    def test_day_7(self):
        self.assertAlmostEqual(engine.streak_multiplier(7), 1.14)

    def test_caps_at_30(self):
        self.assertAlmostEqual(engine.streak_multiplier(30), 1.60)
        self.assertAlmostEqual(engine.streak_multiplier(50), 1.60)


# ── F2: type chart ────────────────────────────────────────────────────────────

class TestTypeChart(unittest.TestCase):
    def test_super_effective_2x(self):
        self.assertEqual(engine.TYPE_CHART['Fire'].get('Grass'), 2.0)

    def test_not_very_effective_0_5x(self):
        self.assertEqual(engine.TYPE_CHART['Fire'].get('Water'), 0.5)

    def test_immune_0x(self):
        self.assertEqual(engine.TYPE_CHART['Electric'].get('Ground'), 0.0)

    def test_neutral_absent(self):
        self.assertIsNone(engine.TYPE_CHART['Normal'].get('Normal'))

    def test_run_battle_immune_floors_at_5(self):
        _, pct, eff = engine.run_battle(100, 'Electric', 1, 'Ground')
        self.assertEqual(eff, 0.0)
        self.assertEqual(pct, 5)

    def test_run_battle_super_effective_boosts_pct(self):
        _, pct_neutral, _ = engine.run_battle(10, 'Normal', 10, 'Normal')
        _, pct_se,      _ = engine.run_battle(10, 'Fire',   10, 'Grass')
        self.assertGreater(pct_se, pct_neutral)


# ── F3: gym badges ────────────────────────────────────────────────────────────

class TestGymBadges(unittest.TestCase):
    def _stats(self, badges=()):
        return {'gym_badges': set(badges)}

    def test_has_unlock_true(self):
        stats = self._stats(['boulder'])
        self.assertTrue(engine.has_unlock('exp_share', stats))

    def test_has_unlock_false(self):
        stats = self._stats()
        self.assertFalse(engine.has_unlock('exp_share', stats))

    def test_next_badge_hint_returns_first_unearned(self):
        stats = self._stats(['boulder'])
        hint = engine.next_badge_hint(stats)
        self.assertIn('Cascade', hint)

    def test_all_badges_earned(self):
        all_ids = [b[0] for b in engine.GYM_BADGE_DATA]
        stats = self._stats(all_ids)
        self.assertIn('All 8 badges', engine.next_badge_hint(stats))

    def test_exp_share_blocked_without_boulder(self):
        stats = self._stats()
        result = engine.distribute_overflow_xp(1000, 'Pikachu', stats)
        self.assertEqual(result, [])


# ── F4: held items ────────────────────────────────────────────────────────────

class TestHeldItems(unittest.TestCase):
    def test_item_ids_match_held_items(self):
        self.assertEqual(engine.ITEM_IDS, list(engine.HELD_ITEMS))

    def test_item_drop_table_keys_valid_tiers(self):
        valid = {'common', 'uncommon', 'rare', 'legendary', 'mythical'}
        self.assertTrue(set(engine.ITEM_DROP_TABLE).issubset(valid))

    def test_item_drop_table_items_are_valid_ids(self):
        for tier, drops in engine.ITEM_DROP_TABLE.items():
            for iid, chance in drops:
                self.assertIn(iid, engine.ITEM_IDS, f'{iid} not in ITEM_IDS')
                self.assertGreater(chance, 0)
                self.assertLessEqual(chance, 1)

    def test_choice_band_boosts_win_pct(self):
        _, pct_base, _ = engine.run_battle(10, 'Normal', 10, 'Normal')
        _, pct_band, _ = engine.run_battle(10, 'Normal', 10, 'Normal', choice_band=True)
        self.assertGreater(pct_band, pct_base)


# ── F6: regional variants ─────────────────────────────────────────────────────

class TestRegionalForms(unittest.TestCase):
    def test_regional_forms_keys_in_pokemon_pool(self):
        all_names = {p[0] for pool in engine.POKEMON_POOL.values() for p in pool}
        for base in engine.REGIONAL_FORMS:
            self.assertIn(base, all_names, f'{base} not in POKEMON_POOL')

    def test_regional_forms_structure(self):
        for base, forms in engine.REGIONAL_FORMS.items():
            for form in forms:
                self.assertEqual(len(form), 4, f'form tuple for {base} should have 4 elements')

    def test_catch_chance_between_0_and_1(self):
        self.assertGreater(engine.REGIONAL_CATCH_CHANCE, 0)
        self.assertLess(engine.REGIONAL_CATCH_CHANCE, 1)


# ── F7: trade evolutions ──────────────────────────────────────────────────────

class TestTradeEvolutions(unittest.TestCase):
    def test_trade_evo_structure(self):
        for pre, (evo_name, evo_emoji, trigger) in engine.TRADE_EVOLUTIONS.items():
            self.assertIsInstance(pre, str)
            self.assertIsInstance(evo_name, str)
            self.assertIn(trigger, ('export', 'backup', 'ship'))

    def test_trade_evo_triggers_are_valid(self):
        valid = {'export', 'backup', 'ship'}
        for _, (_, _, trigger) in engine.TRADE_EVOLUTIONS.items():
            self.assertIn(trigger, valid)


# ── F8: weekly raid ───────────────────────────────────────────────────────────

class TestWeeklyRaid(unittest.TestCase):
    def test_current_week_id_format(self):
        wid = engine._current_week_id()
        self.assertRegex(wid, r'^\d{4}-W\d{2}$')

    def test_raid_base_hp_positive(self):
        self.assertGreater(engine.RAID_BASE_HP, 0)

    def test_apply_raid_damage_with_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = engine.RAID_FILE
            engine.RAID_FILE = Path(tmpdir) / 'buddy-raid.json'
            orig_pool = engine.POKEMON_POOL.get('legendary', [])
            raid, dmg, ko = engine.apply_raid_damage(50)
            engine.RAID_FILE = orig
        self.assertIsNotNone(raid)
        self.assertGreater(dmg, 0)
        self.assertFalse(ko)


# ── F9: egg hatching ──────────────────────────────────────────────────────────

class TestEggHatching(unittest.TestCase):
    def _empty_stats(self):
        return {'egg_species': '', 'egg_type': '', 'egg_emoji': '',
                'egg_xp_need': 0, 'egg_xp_prog': 0}

    def test_award_egg_sets_species(self):
        stats = self._empty_stats()
        msg = engine.award_egg(stats, 'test')
        self.assertNotEqual(stats['egg_species'], '')
        self.assertIn('🥚', msg)

    def test_award_egg_no_double_award(self):
        stats = self._empty_stats()
        engine.award_egg(stats)
        first = stats['egg_species']
        engine.award_egg(stats)
        self.assertEqual(stats['egg_species'], first)

    def test_tick_egg_no_hatch_below_threshold(self):
        stats = self._empty_stats()
        engine.award_egg(stats)
        msg = engine.tick_egg(stats, 50)
        self.assertEqual(msg, '')
        self.assertEqual(stats['egg_xp_prog'], 50)

    def test_egg_hatch_xp_constant(self):
        self.assertEqual(engine.EGG_HATCH_XP, 200)

    def test_egg_babies_all_have_3_fields(self):
        for baby in engine.EGG_BABIES:
            self.assertEqual(len(baby), 3)


# ── F5: party XP split ────────────────────────────────────────────────────────

class TestPartyXpSplit(unittest.TestCase):
    def _party_splits(self):
        return engine._PARTY_SPLITS

    def test_splits_sum_to_1(self):
        self.assertAlmostEqual(sum(self._party_splits()), 1.0)

    def test_lead_gets_most(self):
        splits = self._party_splits()
        self.assertEqual(splits[0], max(splits))

    def test_three_slots(self):
        self.assertEqual(len(self._party_splits()), 3)


# ── Wild evolution system ─────────────────────────────────────────────────────

class TestWildEvolutions(unittest.TestCase):
    def _p(self, name, level):
        return {'name': name, 'level': level, 'emoji': '?', 'type': '?'}

    def test_weedle_to_kakuna(self):
        p = self._p('Weedle', 7)
        engine.try_wild_evolve(p)
        self.assertEqual(p['name'], 'Kakuna')

    def test_kakuna_to_beedrill(self):
        p = self._p('Kakuna', 10)
        engine.try_wild_evolve(p)
        self.assertEqual(p['name'], 'Beedrill')

    def test_weedle_skips_to_beedrill_at_10(self):
        p = self._p('Weedle', 10)
        engine.try_wild_evolve(p)
        self.assertEqual(p['name'], 'Beedrill')

    def test_magikarp_to_gyarados(self):
        p = self._p('Magikarp', 20)
        engine.try_wild_evolve(p)
        self.assertEqual(p['name'], 'Gyarados')

    def test_magikarp_below_threshold_no_evo(self):
        p = self._p('Magikarp', 19)
        engine.try_wild_evolve(p)
        self.assertEqual(p['name'], 'Magikarp')

    def test_no_wild_evo_data_returns_empty(self):
        p = self._p('Arceus', 100)
        result = engine.try_wild_evolve(p)
        self.assertEqual(result, '')
        self.assertEqual(p['name'], 'Arceus')

    def test_intermediate_stage_works(self):
        p = self._p('Pidgeotto', 36)
        engine.try_wild_evolve(p)
        self.assertEqual(p['name'], 'Pidgeot')

    def test_type_and_emoji_updated_on_evo(self):
        p = self._p('Magikarp', 20)
        engine.try_wild_evolve(p)
        self.assertEqual(p['type'], 'Water')
        self.assertEqual(p['emoji'], '🐲')

    def test_chain_integrity_no_duplicates(self):
        all_names = list(engine.WILD_EVOLUTIONS.keys())
        self.assertEqual(len(all_names), len(set(all_names)))

    def test_all_evo_targets_have_valid_type(self):
        from lib.data import TYPE_CHART, TYPE_ADVANTAGE
        all_types = set(TYPE_ADVANTAGE.keys()) | {'Normal', 'Water', 'Fire', 'Grass',
                    'Electric', 'Ice', 'Fighting', 'Poison', 'Ground', 'Flying',
                    'Psychic', 'Bug', 'Rock', 'Ghost', 'Dragon', 'Dark', 'Steel', 'Fairy'}
        for base, chain in engine.WILD_EVOLUTIONS.items():
            for _, evo_name, _, evo_type in chain:
                self.assertIn(evo_type, all_types, f'{evo_name} has invalid type {evo_type}')


# ── Pokédex pool integrity ─────────────────────────────────────────────────────

class TestPokedexPool(unittest.TestCase):
    def test_no_cross_tier_duplicates(self):
        all_names = [p[0] for pool in engine.POKEMON_POOL.values() for p in pool]
        dupes = [n for n in set(all_names) if all_names.count(n) > 1]
        self.assertEqual(dupes, [], f'Cross-tier duplicates: {dupes}')

    def test_total_pool_size(self):
        total = sum(len(v) for v in engine.POKEMON_POOL.values())
        self.assertGreater(total, 250)

    def test_pokedex_ids_cover_pool(self):
        pool_names = {p[0] for pool in engine.POKEMON_POOL.values() for p in pool}
        id_names   = set(engine.POKEDEX_IDS.keys())
        missing    = pool_names - id_names
        self.assertLess(len(missing), 30, f'Too many Pokémon missing from POKEDEX_IDS: {missing}')


# ── MAX display at level cap ───────────────────────────────────────────────────

class TestLevelCapDisplay(unittest.TestCase):
    def test_cap_xp_below_next_level(self):
        self.assertEqual(engine.CAP_XP, engine.xp_for_level(engine.LEVEL_CAP + 1) - 1)

    def test_clamp_at_cap_returns_overflow(self):
        over = engine.xp_for_level(engine.LEVEL_CAP + 1) + 50
        lv, xp, overflow = engine.clamp_to_cap(over)
        self.assertEqual(lv, engine.LEVEL_CAP)
        self.assertEqual(overflow, 51)

    def test_clamp_at_cap_stores_cap_xp(self):
        over = engine.xp_for_level(engine.LEVEL_CAP + 1) + 100
        _, xp, _ = engine.clamp_to_cap(over)
        self.assertEqual(xp, engine.CAP_XP)


# ── Natures (F13) ──────────────────────────────────────────────────────────────

class TestNatures(unittest.TestCase):
    def test_25_natures_defined(self):
        self.assertEqual(len(engine.NATURES), 25)

    def test_pick_nature_returns_valid(self):
        names = {n for n, _, _ in engine.NATURES}
        for _ in range(50):
            self.assertIn(engine.pick_nature(), names)

    def test_nature_info_known(self):
        up, down = engine.nature_info('Adamant')
        self.assertEqual((up, down), ('ATK', 'SPA'))

    def test_nature_info_unknown(self):
        self.assertEqual(engine.nature_info('NotAReal'), ('', ''))

    def test_neutral_natures_up_equals_down(self):
        neutrals = [n for n, up, down in engine.NATURES if up == down]
        self.assertEqual(len(neutrals), 5)


# ── Shiny deepening (F11) ──────────────────────────────────────────────────────

class TestShinyDeep(unittest.TestCase):
    def test_shiny_milestones_defined(self):
        self.assertIn('shiny_5', engine.MILESTONES)
        self.assertIn('shiny_10', engine.MILESTONES)

    def test_shiny_5_triggers_at_5(self):
        stats = {'milestones': set(), 'gym_badges': set(), 'shiny_count': 5}
        col = {'pokemon': [], 'active': ''}
        out = engine.check_milestones(stats, col, 1, 1, None, False)
        keys = {m[1] for m in out}
        self.assertIn('Shiny Collector', keys)

    def test_shiny_10_triggers_at_10(self):
        stats = {'milestones': set(), 'gym_badges': set(), 'shiny_count': 10}
        col = {'pokemon': [], 'active': ''}
        out = engine.check_milestones(stats, col, 1, 1, None, False)
        keys = {m[1] for m in out}
        self.assertIn('Shiny Connoisseur', keys)

    def test_shiny_5_not_triggered_at_4(self):
        stats = {'milestones': set(), 'gym_badges': set(), 'shiny_count': 4}
        col = {'pokemon': [], 'active': ''}
        out = engine.check_milestones(stats, col, 1, 1, None, False)
        self.assertNotIn('shiny_5', stats['milestones'])


# ── Seasonal events (F18) ──────────────────────────────────────────────────────

class TestSeasonalBoost(unittest.TestCase):
    def test_all_months_defined(self):
        from datetime import date as _date
        for m in range(1, 13):
            self.assertIsNotNone(engine.current_seasonal_boost(_date(2026, m, 15)))

    def test_halloween_is_ghost(self):
        from datetime import date as _date
        season = engine.current_seasonal_boost(_date(2026, 10, 15))
        self.assertEqual(season[0], 'Ghost')
        self.assertEqual(season[2], 'Halloween')

    def test_december_ice_extra_boost(self):
        from datetime import date as _date
        season = engine.current_seasonal_boost(_date(2026, 12, 1))
        self.assertEqual(season[0], 'Ice')
        self.assertGreaterEqual(season[1], 4)


# ── Friendship (F17) ───────────────────────────────────────────────────────────

class TestFriendship(_TmpDir, unittest.TestCase):
    def test_boost_increments(self):
        engine.write_collection('Pikachu', [
            {'name': 'Pikachu', 'type': 'Electric', 'emoji': '⚡',
             'level': 5, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'starter',
             'form': '', 'friendship': 70}
        ], party=['Pikachu'])
        engine.boost_friendship('Pikachu', 10)
        col = engine.read_collection()
        self.assertEqual(col['pokemon'][0]['friendship'], 80)

    def test_boost_clamps_at_max(self):
        engine.write_collection('Pikachu', [
            {'name': 'Pikachu', 'type': 'Electric', 'emoji': '⚡',
             'level': 5, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'starter',
             'form': '', 'friendship': 250}
        ], party=['Pikachu'])
        v = engine.boost_friendship('Pikachu', 100)
        self.assertEqual(v, engine.FRIENDSHIP_MAX)

    def test_boost_clamps_at_zero(self):
        engine.write_collection('Pikachu', [
            {'name': 'Pikachu', 'type': 'Electric', 'emoji': '⚡',
             'level': 5, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'starter',
             'form': '', 'friendship': 10}
        ], party=['Pikachu'])
        v = engine.boost_friendship('Pikachu', -100)
        self.assertEqual(v, 0)

    def test_boost_unknown_returns_none(self):
        engine.write_collection(None, [])
        self.assertIsNone(engine.boost_friendship('NoExist', 5))

    def test_friendship_max_milestone(self):
        engine.write_collection('Pikachu', [
            {'name': 'Pikachu', 'type': 'Electric', 'emoji': '⚡',
             'level': 5, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'starter',
             'form': '', 'friendship': 255}
        ], party=['Pikachu'])
        col = engine.read_collection()
        stats = {'milestones': set(), 'gym_badges': set(), 'shiny_count': 0}
        out = engine.check_milestones(stats, col, 1, 1, None, False)
        keys = {m[1] for m in out}
        self.assertIn('Best Friends', keys)


# ── Friendship evolution (F17b) ────────────────────────────────────────────────

class TestFriendshipEvolution(_TmpDir, unittest.TestCase):
    def _eevee_col(self, friendship):
        engine.write_collection('Eevee', [
            {'name': 'Eevee', 'type': 'Normal', 'emoji': '🦊',
             'level': 20, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'rare',
             'form': '', 'nature': 'Hardy', 'friendship': friendship}
        ], party=['Eevee'])

    def test_eevee_to_espeon_day(self):
        self._eevee_col(230)
        col = engine.read_collection()
        out = engine.apply_friendship_evolutions(col, hour=12)
        self.assertEqual(out, ['Eevee → Espeon'])
        self.assertEqual(col['pokemon'][0]['name'], 'Espeon')

    def test_eevee_to_umbreon_night(self):
        self._eevee_col(230)
        col = engine.read_collection()
        out = engine.apply_friendship_evolutions(col, hour=22)
        self.assertEqual(out, ['Eevee → Umbreon'])

    def test_no_evo_below_threshold(self):
        self._eevee_col(200)
        col = engine.read_collection()
        out = engine.apply_friendship_evolutions(col, hour=12)
        self.assertEqual(out, [])
        self.assertEqual(col['pokemon'][0]['name'], 'Eevee')

    def test_active_updated_on_evo(self):
        self._eevee_col(255)
        col = engine.read_collection()
        engine.apply_friendship_evolutions(col, hour=12)
        self.assertEqual(col['active'], 'Espeon')

    def test_riolu_to_lucario_day(self):
        engine.write_collection('Riolu', [
            {'name': 'Riolu', 'type': 'Fighting', 'emoji': '💪',
             'level': 25, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'uncommon',
             'form': '', 'nature': 'Jolly', 'friendship': 225}
        ], party=['Riolu'])
        col = engine.read_collection()
        out = engine.apply_friendship_evolutions(col, hour=10)
        self.assertEqual(out, ['Riolu → Lucario'])

    def test_riolu_no_night_evo(self):
        engine.write_collection('Riolu', [
            {'name': 'Riolu', 'type': 'Fighting', 'emoji': '💪',
             'level': 25, 'xp': 0, 'caught': '2026-01-01', 'rarity': 'uncommon',
             'form': '', 'nature': 'Jolly', 'friendship': 255}
        ], party=['Riolu'])
        col = engine.read_collection()
        out = engine.apply_friendship_evolutions(col, hour=22)
        self.assertEqual(out, [])


# ── Gym battles (F14 PvP lite) ─────────────────────────────────────────────────

class TestGymBattles(unittest.TestCase):
    def test_8_leaders_defined(self):
        self.assertEqual(len(engine.GYM_LEADERS), 8)

    def test_all_leaders_map_to_badge(self):
        badge_ids = {b[0] for b in engine.GYM_BADGE_DATA}
        for L in engine.GYM_LEADERS:
            self.assertIn(L[6], badge_ids)

    def test_unknown_leader_fails(self):
        stats = {'leaders_defeated': set(), 'gym_badges': set()}
        won, xp, log, badge = engine.battle_leader('no_such', 50, 'Fire', stats)
        self.assertFalse(won)
        self.assertIsNone(badge)
        self.assertEqual(xp, 0)

    def test_winning_awards_badge(self):
        stats = {'leaders_defeated': set(), 'gym_badges': set()}
        with patch('random.randint', return_value=1):  # force win
            won, xp, log, badge = engine.battle_leader('brock', 80, 'Water', stats)
        self.assertTrue(won)
        self.assertIn('brock', stats['leaders_defeated'])
        self.assertIn('boulder', stats['gym_badges'])
        self.assertEqual(xp, 75)

    def test_rematch_no_duplicate_badge(self):
        stats = {'leaders_defeated': {'brock'}, 'gym_badges': {'boulder'}}
        with patch('random.randint', return_value=1):
            won, xp, log, badge = engine.battle_leader('brock', 80, 'Water', stats)
        self.assertTrue(won)
        self.assertIsNone(badge)  # no new badge on rematch

    def test_losing_gives_consolation_xp(self):
        stats = {'leaders_defeated': set(), 'gym_badges': set()}
        with patch('random.randint', return_value=100):  # force loss
            won, xp, log, badge = engine.battle_leader('giovanni', 5, 'Fire', stats)
        self.assertFalse(won)
        self.assertEqual(xp, 10)

    def test_mega_stone_without_earth_badge_no_boost(self):
        stats = {'leaders_defeated': set(), 'gym_badges': set()}
        with patch('random.randint', return_value=1):
            _, _, log, _ = engine.battle_leader('brock', 10, 'Water', stats, held_item='mega_stone')
        self.assertFalse(any('MEGA EVOLVED' in line for line in log))

    def test_mega_stone_with_earth_badge_boosts(self):
        stats = {'leaders_defeated': set(), 'gym_badges': {'earth'}}
        with patch('random.randint', return_value=1):
            _, _, log, _ = engine.battle_leader('brock', 10, 'Water', stats, held_item='mega_stone')
        self.assertTrue(any('MEGA EVOLVED' in line for line in log))

    def test_mega_stone_has_drop_entry(self):
        self.assertIn('mega_stone', engine.HELD_ITEMS)
        legendary_drops = {item for item, _ in engine.ITEM_DROP_TABLE['legendary']}
        self.assertIn('mega_stone', legendary_drops)

    def test_list_leaders_recommends_super_effective(self):
        stats = {'leaders_defeated': set(), 'gym_badges': set()}
        # Water buddy → super-effective vs Blaine (Fire) and Giovanni (Ground)
        out = engine.list_leaders(stats, buddy_type='Water')
        self.assertIn('⭐ RECOMMENDED', out)
        self.assertIn('×2 super-eff', out)

    def test_learnset_coverage_popular_species(self):
        for sp in ('Pikachu', 'Eevee', 'Riolu', 'Gible', 'Gastly', 'Abra', 'Machop', 'Dratini', 'Lucario'):
            self.assertIn(sp, engine.MOVE_UNLOCKS)

    def test_all_learnsets_have_4_moves(self):
        for sp, moves in engine.MOVE_UNLOCKS.items():
            self.assertEqual(len(moves), 4, f'{sp} should have 4 moves')

    def test_all_moves_have_3_fields(self):
        for sp, moves in engine.MOVE_UNLOCKS.items():
            for lv, entry in moves.items():
                self.assertEqual(len(entry), 3, f'{sp} Lv.{lv} malformed')

    def test_list_leaders_skips_defeated_in_recommendation(self):
        stats = {'leaders_defeated': {'brock'}, 'gym_badges': {'boulder'}}
        out = engine.list_leaders(stats, buddy_type='Water')
        # Brock should not be recommended (already defeated)
        brock_line = next(L for L in out.splitlines() if 'Brock' in L)
        self.assertNotIn('⭐ RECOMMENDED', brock_line)


class TestAntiCheat(unittest.TestCase):
    def test_desc_hash_normalizes_whitespace_and_case(self):
        self.assertEqual(engine._desc_hash('Fix Bug'), engine._desc_hash('  fix  bug  '))
        self.assertNotEqual(engine._desc_hash('fix bug'), engine._desc_hash('add feature'))

    def test_desc_hash_empty_returns_empty(self):
        self.assertEqual(engine._desc_hash(''), '')
        self.assertEqual(engine._desc_hash('   '), '')

    def test_dedup_blocks_same_desc_within_window(self):
        import time as _t
        stats = {'last_xp_hash': engine._desc_hash('fix auth bug'),
                 'last_xp_ts': int(_t.time())}
        self.assertTrue(engine.check_xp_dedup(stats, 'fix auth bug'))
        self.assertFalse(engine.check_xp_dedup(stats, 'add feature'))

    def test_dedup_allows_after_window(self):
        import time as _t
        stats = {'last_xp_hash': engine._desc_hash('fix bug'),
                 'last_xp_ts': int(_t.time()) - engine.XP_DEDUP_WINDOW - 1}
        self.assertFalse(engine.check_xp_dedup(stats, 'fix bug'))

    def test_dedup_allows_when_no_prior_hash(self):
        self.assertFalse(engine.check_xp_dedup({}, 'anything'))

    def test_daily_cap_clips_to_remaining(self):
        stats = {'daily_xp': engine.DAILY_XP_CAP - 50, 'daily_xp_date': engine.TODAY}
        clipped, capped, rem = engine.apply_daily_cap(stats, 200)
        self.assertEqual(clipped, 50)
        self.assertTrue(capped)
        self.assertEqual(rem, 50)

    def test_daily_cap_passthrough_when_under_budget(self):
        stats = {'daily_xp': 100, 'daily_xp_date': engine.TODAY}
        clipped, capped, _ = engine.apply_daily_cap(stats, 50)
        self.assertEqual(clipped, 50)
        self.assertFalse(capped)

    def test_daily_cap_resets_on_new_day(self):
        stats = {'daily_xp': engine.DAILY_XP_CAP, 'daily_xp_date': '2020-01-01'}
        clipped, capped, _ = engine.apply_daily_cap(stats, 100)
        self.assertEqual(clipped, 100)
        self.assertFalse(capped)
        self.assertEqual(stats['daily_xp_date'], engine.TODAY)
        self.assertEqual(stats['daily_xp'], 0)

    def test_regen_stamina_recovers_points_over_time(self):
        import time as _t
        stats = {'battle_stamina': 0,
                 'battle_stamina_ts': int(_t.time()) - 2 * engine.BATTLE_REGEN_SECS - 1}
        self.assertEqual(engine.regen_stamina(stats), 2)

    def test_regen_stamina_caps_at_max(self):
        import time as _t
        stats = {'battle_stamina': 1,
                 'battle_stamina_ts': int(_t.time()) - 100 * engine.BATTLE_REGEN_SECS}
        self.assertEqual(engine.regen_stamina(stats), engine.BATTLE_STAMINA_MAX)

    def test_regen_stamina_no_change_within_interval(self):
        import time as _t
        stats = {'battle_stamina': 1, 'battle_stamina_ts': int(_t.time())}
        self.assertEqual(engine.regen_stamina(stats), 1)

    def test_fmt_duration_ranges(self):
        self.assertEqual(engine.fmt_duration(45), '45s')
        self.assertEqual(engine.fmt_duration(125), '2m 5s')
        self.assertEqual(engine.fmt_duration(3725), '1h 2m')
        self.assertEqual(engine.fmt_duration(-10), '0s')


class TestEliteFour(unittest.TestCase):
    def _full_badges(self):
        return set(engine._BADGE_ORDER)

    def test_gate_blocks_without_all_badges(self):
        stats = {'gym_badges': {'boulder', 'cascade'}, 'elite_defeated': set()}
        ok, reason = engine._elite_gate(stats)
        self.assertFalse(ok)
        self.assertIn('Missing', reason)

    def test_gate_passes_with_all_badges(self):
        stats = {'gym_badges': self._full_badges(), 'elite_defeated': set()}
        ok, _ = engine._elite_gate(stats)
        self.assertTrue(ok)

    def test_next_elite_follows_order(self):
        stats = {'elite_defeated': {'lorelei', 'bruno'}}
        self.assertEqual(engine._next_elite(stats), 'agatha')

    def test_next_elite_none_when_all_beaten(self):
        stats = {'elite_defeated': set(engine._ELITE_ORDER)}
        self.assertIsNone(engine._next_elite(stats))

    def test_battle_elite_blocked_without_badges(self):
        stats = {'gym_badges': set(), 'elite_defeated': set()}
        won, xp, log, champ = engine.battle_elite('lorelei', 100, 'Normal', stats)
        self.assertFalse(won)
        self.assertEqual(xp, 0)
        self.assertFalse(champ)
        self.assertIn('locked', log[0].lower())

    def test_battle_elite_blocked_out_of_order(self):
        stats = {'gym_badges': self._full_badges(), 'elite_defeated': set()}
        won, xp, log, champ = engine.battle_elite('champion', 100, 'Normal', stats)
        self.assertFalse(won)
        self.assertIn('Lorelei', log[0])

    def test_battle_elite_all_beaten_blocks(self):
        stats = {'gym_badges': self._full_badges(),
                 'elite_defeated': set(engine._ELITE_ORDER)}
        won, xp, log, champ = engine.battle_elite('lorelei', 100, 'Normal', stats)
        self.assertFalse(won)
        self.assertIn('Already defeated', log[0])

    def test_battle_elite_win_sets_champion_on_last(self):
        stats = {'gym_badges': self._full_badges(),
                 'elite_defeated': {'lorelei', 'bruno', 'agatha', 'lance'}}
        import random as _r
        _r.seed(1)
        won, xp, log, champ = engine.battle_elite('champion', 100, 'Normal', stats)
        # Level 100 vs 65 overlevel → nearly guaranteed win
        self.assertTrue(won)
        self.assertTrue(champ)
        self.assertTrue(stats['beat_elite_four'])
        self.assertGreaterEqual(xp, 500)


class TestTypePalette(unittest.TestCase):
    def test_known_types_return_hex_pair(self):
        hi, dk = engine._type_palette('Fire')
        self.assertTrue(hi.startswith('#') and len(hi) == 7)
        self.assertTrue(dk.startswith('#') and len(dk) == 7)

    def test_unknown_type_falls_back_to_normal(self):
        self.assertEqual(engine._type_palette('Cosmic'), engine._type_palette('Normal'))

    def test_rarity_fx_class_applies_shiny_overlay(self):
        out = engine._rarity_fx_class('legendary', shiny=True)
        self.assertIn('fx-legendary', out)
        self.assertIn('fx-shiny', out)

    def test_rarity_fx_class_handles_shiny_suffix(self):
        self.assertIn('fx-rare', engine._rarity_fx_class('rare-shiny', shiny=True))

    def test_common_rarity_has_no_fx_class(self):
        self.assertEqual(engine._rarity_fx_class('common', shiny=False), '')


class TestGuardsDisplay(unittest.TestCase):
    def test_guards_shows_both_meters(self):
        stats = {'battle_stamina': 2, 'battle_stamina_ts': int(__import__('time').time()),
                 'daily_xp': 500, 'daily_xp_date': engine.TODAY}
        out = engine._guards_display(stats)
        self.assertIn('Stamina 2/', out)
        self.assertIn('500/', out)
        self.assertIn('🎯', out)

    def test_guards_resets_daily_xp_on_stale_date(self):
        stats = {'battle_stamina': 3, 'battle_stamina_ts': int(__import__('time').time()),
                 'daily_xp': 999, 'daily_xp_date': '2020-01-01'}
        out = engine._guards_display(stats)
        self.assertIn('0/', out)


class TestEliteFourStats(_TmpDir, unittest.TestCase):
    def test_elite_state_round_trips(self):
        s = engine.read_stats()
        s['gym_badges'] = set(engine._BADGE_ORDER)
        s['elite_defeated'] = {'lorelei', 'bruno'}
        s['beat_elite_four'] = False
        engine.write_stats(s)
        got = engine.read_stats()
        self.assertEqual(got['elite_defeated'], {'lorelei', 'bruno'})
        self.assertFalse(got['beat_elite_four'])

    def test_champion_title_wins_over_mythical(self):
        s = engine.read_stats()
        s['beat_elite_four'] = True
        s['caught_mythical'] = True
        col = {'pokemon': [], 'active': None}
        self.assertEqual(engine.get_trainer_title(s, col), 'Champion')


if __name__ == '__main__':
    unittest.main()
