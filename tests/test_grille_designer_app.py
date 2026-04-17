from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1]
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import grille_designer_app as app  # noqa: E402


class GrilleDesignerAppTests(unittest.TestCase):
    def test_default_state_imports_week_from_documentation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tool_dir = root / "LCN-Tools" / "Concepteur-Grille"
            tool_dir.mkdir(parents=True)
            (tool_dir / "web").mkdir()

            docs_dir = root / "LCN-Documentation"
            docs_dir.mkdir(parents=True)
            (docs_dir / "SPEC-LCN-LIQUIDSOAP.md").write_text(
                "### 8.7 Traduction horaire actuelle de la grille\n"
                "#### Lundi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Mardi\n"
                "- `00:00 → 18:00` : `La Grande Nuit`\n"
                "- `18:00` : `Home Taping Is Killing Music` (1 épisode RANDOM)\n"
                "- après Home Taping Is Killing Music jusqu’à `24:00` : `Noise de l’aprème`\n"
                "#### Mercredi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Jeudi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Vendredi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Samedi\n"
                "- `00:00 → 14:00` : `La Grande Nuit`\n"
                "- `14:00` : `L’instinct mode` (1 épisode)\n"
                "- après Instinct Mode jusqu’à `16:00` : `Beats & Flow`\n"
                "- `16:00 → 24:00` : `Les chats dans la courée`\n"
                "#### Dimanche\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n",
                encoding="utf-8",
            )
            (docs_dir / "radio.liq.txt").write_text(
                'htikm = tag_show("Home Taping Is Killing Music", "editorial_event", "false", mk_dir_pool("/srv/radio/emissions/HTIKM"))\n'
                'beats_et_flow = tag_show("Beats & Flow", "music_block", "false", mk_pool("/srv/radio/pools/beats-et-flow.m3u"))\n'
                'p_htikm = predicate.once({2w and 18h-23h39})\n',
                encoding="utf-8",
            )

            state = app.build_default_state(tool_dir)

        tue_event = state["week"]["tue"]["events"][0]
        sat_block = state["week"]["sat"]["blocks"][1]
        self.assertEqual(tue_event["title"], "Home Taping Is Killing Music")
        self.assertEqual(tue_event["pendingUntil"], "19:00")
        self.assertEqual(tue_event["liquidsoapPendingUntil"], "23:39")
        self.assertEqual(sat_block["title"], "Beats & Flow")
        self.assertEqual(sat_block["startTime"], "14:05")

    def test_time_to_minutes_accepts_24h(self) -> None:
        self.assertEqual(app.time_to_minutes("00:00"), 0)
        self.assertEqual(app.time_to_minutes("14:30"), 870)
        self.assertEqual(app.time_to_minutes("24:00"), 1440)

    def test_default_state_contains_full_week(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = app.build_default_state(Path(tmpdir))

        self.assertEqual(list(state["week"].keys()), app.DAY_ORDER)
        self.assertEqual(state["week"]["mon"]["blocks"][0]["title"], "La Grande Nuit")
        self.assertEqual(state["week"]["sat"]["events"][0]["title"], "Console-toi")
        self.assertEqual(state["week"]["mon"]["events"][0]["pendingUntil"], "07:05")
        self.assertEqual(state["week"]["wed"]["events"][1]["pendingUntil"], "15:00")
        self.assertEqual(state["runtime"]["liveInput"]["port"], 8005)
        self.assertEqual(state["rotationPolicy"]["artistCooldownMinutes"], 90)

    def test_jsonl_export_contains_slots_and_dressing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = app.normalize_state(app.build_default_state(Path(tmpdir)), Path(tmpdir))

        content = app.state_to_jsonl_text(state)
        self.assertIn('"recordType": "dressing"', content)
        self.assertIn('"recordType": "slot"', content)
        self.assertIn('"recordType": "show_profile"', content)
        self.assertIn('"recordType": "runtime_output"', content)
        self.assertIn('"recordType": "rotation_policy"', content)
        self.assertIn('"title": "Messe Noire"', content)

    def test_service_initializes_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir)
            (tool_dir / "web").mkdir()
            service = app.DesignerService(tool_dir)

            self.assertTrue(service.state_path.is_file())
            self.assertTrue(service.jsonl_path.is_file())
            self.assertEqual(service.state_path, tool_dir / app.PRIVATE_DIRNAME / app.JSON_FILENAME)
            self.assertEqual(service.jsonl_path, tool_dir / app.PRIVATE_DIRNAME / app.JSONL_FILENAME)

            payload = json.loads(service.state_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["app"], app.APP_NAME)

    def test_normalize_state_reimports_week_when_documentation_fingerprint_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tool_dir = root / "LCN-Tools" / "Concepteur-Grille"
            tool_dir.mkdir(parents=True)
            (tool_dir / "web").mkdir()

            docs_dir = root / "LCN-Documentation"
            docs_dir.mkdir(parents=True)
            (docs_dir / "SPEC-LCN-LIQUIDSOAP.md").write_text(
                "### 8.7 Traduction horaire actuelle de la grille\n"
                "#### Lundi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Mardi\n"
                "- `00:00 → 18:00` : `La Grande Nuit`\n"
                "- `18:00` : `Home Taping Is Killing Music` (1 épisode RANDOM)\n"
                "- après Home Taping Is Killing Music jusqu’à `24:00` : `Noise de l’aprème`\n"
                "#### Mercredi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Jeudi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Vendredi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Samedi\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n"
                "#### Dimanche\n"
                "- `00:00 → 24:00` : `La Grande Nuit`\n",
                encoding="utf-8",
            )
            (docs_dir / "radio.liq.txt").write_text(
                'p_htikm = predicate.once({2w and 18h-23h39})\n',
                encoding="utf-8",
            )

            state = app.build_default_state(tool_dir)
            state["documentationFingerprint"] = "obsolete"
            state["week"]["tue"]["events"] = []

            normalized = app.normalize_state(state, tool_dir)

        self.assertEqual(normalized["week"]["tue"]["events"][0]["title"], "Home Taping Is Killing Music")

    def test_build_catalog_parses_tags_from_csv_and_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tool_dir = root / "LCN-Tools" / "Concepteur-Grille"
            tool_dir.mkdir(parents=True)
            (tool_dir / "web").mkdir()
            (tool_dir / "data").mkdir()

            (tool_dir / "data" / "genres_bibliotheque_complete.csv").write_text(
                '"fichier","genre","artiste","album","duree_secondes"\n'
                '"/tmp/a.mp3","ambient","Artiste A","Album A","120"\n'
                '"/tmp/b.mp3","noise-rock","Artiste B","Album B","300"\n',
                encoding="utf-8",
            )

            docs_dir = root / "LCN-Documentation"
            docs_dir.mkdir(parents=True)
            (docs_dir / "LCN-CARTOGRAPHIE-GENRES.md").write_text(
                "# Test\n\n"
                "| Tag observé | Tag normalisé | Occurrences | Bloc principal | Blocs secondaires possibles | Remarques |\n"
                "|---|---|---:|---|---|---|\n"
                "| ambient | ambiant | 1 | La Grande Nuit | Le réveil lent du chat | test |\n"
                "| noise-rock | noise-rock | 1 | Noise de l’aprème | Messe Noire | test |\n",
                encoding="utf-8",
            )

            catalog = app.build_catalog(tool_dir)

            self.assertEqual(catalog["tagLibrary"]["trackCount"], 2)
            self.assertEqual(len(catalog["tagLibrary"]["observedTags"]), 2)
            self.assertEqual(len(catalog["tagLibrary"]["trackRecords"]), 2)
            self.assertEqual(len(catalog["tagLibrary"]["tracksByTag"]["ambiant"]), 1)
            self.assertTrue(catalog["tagLibrary"]["sourceCsv"].endswith("genres_bibliotheque_complete.csv"))
            self.assertEqual(catalog["tagLibrary"]["trackRecords"][0]["artist"], "Artiste A")
            state = app.normalize_state(app.build_default_state(tool_dir), tool_dir)
            content = app.state_to_jsonl_text(state)
            self.assertIn('"recordType": "track"', content)
            la_grande_nuit = next(
                profile for profile in catalog["showProfiles"]
                if profile["showId"] == "la-grande-nuit"
            )
            self.assertEqual(la_grande_nuit["primaryTags"][0]["tag"], "ambiant")
            self.assertEqual(la_grande_nuit["generatorMode"], "tag_pool")

    def test_genre_catalog_prefers_private_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir)
            (tool_dir / app.PRIVATE_DIRNAME).mkdir(parents=True)
            (tool_dir / app.DATA_DIRNAME).mkdir(parents=True)

            private_csv = tool_dir / app.PRIVATE_DIRNAME / "genres_bibliotheque_complete.csv"
            legacy_csv = tool_dir / app.DATA_DIRNAME / "genres_bibliotheque_complete.csv"
            private_csv.write_text('"fichier","genre"\n"/tmp/private.mp3","ambient"\n', encoding="utf-8")
            legacy_csv.write_text('"fichier","genre"\n"/tmp/legacy.mp3","noise"\n', encoding="utf-8")

            csv_path = app.find_genre_catalog_csv_path(tool_dir)

            self.assertEqual(csv_path, private_csv)

    def test_runtime_defaults_and_show_paths_can_come_from_private_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_dir = Path(tmpdir)
            (tool_dir / app.PRIVATE_DIRNAME).mkdir(parents=True)
            (tool_dir / "web").mkdir()
            (tool_dir / app.PRIVATE_DIRNAME / app.CONFIG_FILENAME).write_text(
                json.dumps(
                    {
                        "runtime": {
                            "paths": {
                                "musicLibraryRoot": "/srv/music",
                                "radioRoot": "/srv/radio",
                                "poolsDir": "/srv/radio/pools",
                                "emissionsDir": "/srv/radio/emissions",
                                "jinglesDir": "/srv/radio/jingles",
                                "reclamesDir": "/srv/radio/reclames",
                                "logsDir": "/srv/radio/logs",
                                "webRoot": "/srv/www",
                                "currentShowJson": "/srv/www/current-show.json",
                                "nowPlayingJson": "/srv/www/nowplaying.json",
                                "historyDir": "/srv/www/history",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            runtime = app.load_runtime_defaults(tool_dir)
            shows = app.resolve_show_definitions(tool_dir)
            by_id = {item["id"]: item for item in shows}

            self.assertEqual(runtime["paths"]["musicLibraryRoot"], "/srv/music")
            self.assertEqual(by_id["la-grande-nuit"]["defaultSourcePath"], "/srv/radio/pools/la-grande-nuit.m3u")
            self.assertEqual(by_id["l-instinct-mode"]["defaultSourcePath"], "/srv/radio/emissions/instinctmode")


if __name__ == "__main__":
    unittest.main()
