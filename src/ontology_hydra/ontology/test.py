import tempfile
from itertools import islice
from pathlib import Path

from ontology_hydra.ontology.agents.proposer.proposer import propose_changes
from ontology_hydra.ontology.agents.updater.updater import apply_proposal
from ontology_hydra.ontology.state.models import DEFAULT_ONTOLOGY_STATE
from ontology_hydra.utils.cache import DirectoryCache
from ontology_hydra.utils.general import track_usage

print("Beginning...")

state = DEFAULT_ONTOLOGY_STATE

N_EPOCHS = 5
BATCH_SIZE = 50

INTENT = "I want to find criminal connections"

TAKE_N_SAMPLES = 500
SAMPLES_PATH = Path("/Users/adrian/Desktop/Datasets/enron_mail/maildir")

SAMPLES = [
    p.read_text(encoding="utf-8", errors="ignore")
    for p in islice(SAMPLES_PATH.glob("**/*."), TAKE_N_SAMPLES)
]

print(len(SAMPLES), "samples loaded...")

cache = DirectoryCache(Path(tempfile.mkdtemp(prefix="ontology-hydra.")))

print(f"Cache path: {cache.path}")


for epoch in range(N_EPOCHS):
    print(f"-> Epoch {epoch}")
    for i in range(0, len(SAMPLES), BATCH_SIZE):
        print(f"--> Batch {i}")
        samples = SAMPLES[i : i + BATCH_SIZE]

        with track_usage() as tracker:
            proposal = propose_changes(ontology=state, samples=samples, intent=INTENT)
            cache.write_model((f"epoch[{epoch}]", f"batch[{i}]", "proposal.json"), proposal)

            output = apply_proposal(ontology=state, proposal=proposal)
            cache.write_model((f"epoch[{epoch}]", f"batch[{i}]", "updated_state.json"), output)
        # TODO: try to apply proposal here. If it does not work, send it back.

        # cache.write_model((f"e{epoch}", f"b{i}", "proposal.json"), proposal)
        print(tracker.usage)

        # ranked_proposals = rank_proposals(proposals=proposals, state=state, intent=INTENT)
        # best_proposal = ranked_proposals[0]
