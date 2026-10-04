# Fuzzy classification

Evidence-alignment ratios map to overlapping triangular membership functions. Required and preferred skills are weighted; absent benchmark groups must not create artificial penalties. GitHub activity uses recent non-fork pushes when evidence is available. Source availability and content completeness are distinct.

Membership degrees explain linguistic labels; they are not confidence probabilities or probabilities of professional competence. The legacy API field `profile_completeness_score` currently measures supplied-source coverage; per-source `content_completeness` flags describe content separately. Do not interpret source coverage as a quality score.

[fuzzy_logic.py](../../backend/app/modules/fuzzy_logic.py) owns exact boundaries and weights. Test zero/full matches, boundaries, empty groups, ties, and unknown inputs. Do not claim empirical calibration without evaluation.
