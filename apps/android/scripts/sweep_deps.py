#!/usr/bin/env python3
"""
Sweep des dépendances Gradle vs imports Kotlin pour le module Android.

Détecte en local (sans builder) les modules qui importent une API sans
avoir déclaré la dépendance correspondante dans build.gradle.kts. Évite
les ping-pong CI à 5 min par itération.

Usage:
    python3 apps/android/scripts/sweep_deps.py

Limites :
- Suit uniquement les déps directes du module (pas les `api(project(...))`
  transitifs). Faux positif possible si une API arrive via api transitif.
- Catalogue IMPORT_TO_DEP est manuel ; à compléter pour chaque nouveau
  groupe d'imports.
"""
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent  # apps/android

IMPORT_TO_DEP = {
    "timber.log": ["libs.timber"],
    "androidx.core.content.FileProvider": ["libs.androidx.core.ktx"],
    "androidx.core.content.ContextCompat": ["libs.androidx.core.ktx"],
    "androidx.core.app": ["libs.androidx.core.ktx"],
    "com.google.common.truth": ["libs.truth", "libs.bundles.testing"],
    "org.junit.jupiter": ["libs.junit.jupiter", "libs.bundles.testing"],
    "io.mockk": ["libs.mockk", "libs.bundles.testing"],
    "app.cash.turbine": ["libs.turbine", "libs.bundles.testing"],
    "kotlinx.coroutines": ["libs.kotlinx.coroutines.core", "libs.kotlinx.coroutines.android"],
    "androidx.lifecycle": ["libs.bundles.lifecycle"],
    "androidx.navigation": ["libs.androidx.navigation.compose"],
    "androidx.activity.compose": ["libs.androidx.activity.compose"],
    "androidx.work": ["libs.androidx.work.runtime"],
    "androidx.room": ["libs.androidx.room.runtime", "libs.androidx.room.ktx"],
    "androidx.datastore": ["libs.androidx.datastore.preferences"],
    "androidx.security.crypto": ["libs.androidx.security.crypto"],
    "androidx.biometric": ["libs.androidx.biometric"],
    "androidx.hilt.work": ["hilt-work"],
    "com.google.firebase": ["libs.firebase.messaging", "libs.firebase.crashlytics"],
    "com.google.android.play.core.appupdate": ["libs.play.app.update.lib"],
    "coil": ["libs.coil.compose"],
    "io.coil": ["libs.coil.compose"],
    "androidx.camera": ["libs.camerax", "androidx.camera:camera-core"],
    "com.google.mlkit": ["libs.mlkit.barcode", "com.google.mlkit:barcode-scanning"],
}


def normalize_raw_gav(deps):
    """Ajoute les GAVs sous forme tronquée pour matcher avec IMPORT_TO_DEP."""
    out = set(deps)
    for d in deps:
        if ":" in d and not d.startswith("libs."):
            # ex: "androidx.camera:camera-core:1.4.1" → "androidx.camera:camera-core"
            parts = d.rsplit(":", 1)
            if len(parts) == 2:
                out.add(parts[0])
    return out


def discover_modules():
    settings = (ROOT / "settings.gradle.kts").read_text()
    names = re.findall(r'include\(":([^"]+)"\)', settings)
    mods = {}
    for n in names:
        p = ROOT / n.replace(":", "/") / "build.gradle.kts"
        if p.exists():
            mods[n] = p
    return mods


def collect_deps(content):
    """Retourne l'ensemble des alias / strings déclarés en deps (toutes scopes)."""
    deps = set(re.findall(r'libs\.(?:bundles\.)?[\w\.]+', content))
    deps.update(re.findall(r'"([^"]+:[^"]+:[^"]+)"', content))
    deps.update(m.group(1) for m in re.finditer(r'"androidx\.hilt:(hilt-work)', content))
    return deps


def collect_project_deps(content):
    """Retourne l'ensemble des `project(":...")` (peu importe la scope)."""
    return set(re.findall(r'project\(":([^"]+)"\)', content))


def has_dep(declared, aliases):
    return any(a in declared for a in aliases)


def main():
    modules = discover_modules()
    contents = {n: p.read_text() for n, p in modules.items()}
    direct_deps = {n: collect_deps(c) for n, c in contents.items()}
    project_deps = {n: collect_project_deps(c) for n, c in contents.items()}

    # Build api-export map : module → set of api'd deps (libs + projects)
    api_exports = {}
    for n, content in contents.items():
        exports = set()
        for line in content.splitlines():
            if line.lstrip().startswith("api("):
                exports.update(re.findall(r'libs\.(?:bundles\.)?[\w\.]+', line))
                exports.update(re.findall(r'project\(":([^"]+)"\)', line))
        api_exports[n] = exports

    def transitive_deps(name, seen=None):
        if seen is None:
            seen = set()
        if name in seen:
            return set()
        seen.add(name)
        out = set(direct_deps.get(name, set()))
        for proj in project_deps.get(name, set()):
            # follow only if api-exported by parent? No — every project dep
            # gives us at least its `api(...)` exports transitively
            ex = api_exports.get(proj, set())
            out.update(ex)
            for ex_proj in [e for e in ex if not e.startswith("libs.") and ":" in e or "-" in e]:
                out.update(transitive_deps(ex_proj, seen))
        return out

    issues = []
    for n in modules:
        all_deps = normalize_raw_gav(transitive_deps(n))
        for sub in ("src/main/kotlin", "src/main/java", "src/test/kotlin", "src/test/java"):
            d = ROOT / n.replace(":", "/") / sub
            if not d.exists():
                continue
            is_test = sub.startswith("src/test")
            for kt in d.rglob("*.kt"):
                try:
                    txt = kt.read_text()
                except Exception:
                    continue
                for imp in re.findall(r'^import\s+([\w\.]+)', txt, re.M):
                    for prefix, aliases in IMPORT_TO_DEP.items():
                        if imp == prefix or imp.startswith(prefix + "."):
                            if not has_dep(all_deps, aliases):
                                issues.append(
                                    (n, str(kt.relative_to(ROOT)), imp, aliases, is_test)
                                )
                            break

    grouped = defaultdict(set)
    for n, _file, imp, aliases, is_test in issues:
        grouped[n].add(("TEST" if is_test else "MAIN", imp, tuple(aliases)))

    print(f"# Sweep deps: {sum(len(v) for v in grouped.values())} issues uniques sur {len(grouped)} modules\n")
    for n in sorted(grouped):
        print(f"## :{n}")
        for tag, imp, aliases in sorted(grouped[n]):
            print(f"  [{tag}] {imp} → besoin {list(aliases)}")
        print()
    if not grouped:
        print("OK — toutes les déps Gradle couvrent les imports Kotlin détectés.")


if __name__ == "__main__":
    main()
