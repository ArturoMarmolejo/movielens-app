"""One-time patch for app.py: pass title and year to the poster function (for the TV fallback).
Run from the app folder:  python3 apply_tv_fallback.py     (makes app.py.bak2; changes nothing if any spot is missing)
"""
import shutil, sys

a = open("app.py").read()

def edit(text, old, new, label):
    if text.count(old) != 1:
        sys.exit(f"STOP: could not find exactly one place for: {label}. No files changed.")
    return text.replace(old, new)

a = edit(a, "posters.show([(caption_fn(r), ids.get(int(r.movieId))) for r in d.itertuples()], per_row=per_row)",
            "posters.show([(caption_fn(r), ids.get(int(r.movieId)), r.title_clean, r.release_year) for r in d.itertuples()], per_row=per_row)", "top movies / finder")
a = edit(a, "posters.show([(lbl, ids.get(int(r.movieId))) for _, lbl, r in picks], per_row=2, width=170)",
            "posters.show([(lbl, ids.get(int(r.movieId)), r.title_clean, r.release_year) for _, lbl, r in picks], per_row=2, width=170)", "compare")
a = edit(a, "posters.show([(t, ids.get((t.lower(), y))) for t, y in pairs], per_row=3, width=120)",
            "posters.show([(t, ids.get((t.lower(), y)), t, y) for t, y in pairs], per_row=3, width=120)", "similar movies")
a = edit(a, "posters.show([(t, ids.get((t.lower(), y))) for t, y in top5], per_row=3, width=120)",
            "posters.show([(t, ids.get((t.lower(), y)), t, y) for t, y in top5], per_row=3, width=120)", "user picks")

shutil.copy("app.py", "app.py.bak2")
open("app.py", "w").write(a)
print("Done. Backup: app.py.bak2")
