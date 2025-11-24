import tempfile
from itertools import islice
from pathlib import Path

from ontology_hydra.ontology.agents.proposer.proposer import Proposal, propose_changes
from ontology_hydra.ontology.state.models import DEFAULT_ONTOLOGY_STATE, OntologyState
from ontology_hydra.ontology.state.ops.apply import apply
from ontology_hydra.utils.cache import DirectoryCache

print("Beginning...")

state = DEFAULT_ONTOLOGY_STATE

N_EPOCHS = 5
BATCH_SIZE = 50

INTENT = "I want to find criminal connections"

TAKE_N_SAMPLES = 500
SAMPLES_PATH = Path("/home/adrian/Documents/datasets/enron_mail/maildir")

SAMPLES = [
    p.read_text(encoding="utf-8", errors="ignore")
    for p in islice(SAMPLES_PATH.glob("**/*."), TAKE_N_SAMPLES)
]

print("Samples loaded...")

cache = DirectoryCache(Path(tempfile.mkdtemp(prefix="ontology-hydra.")))

print(f"Cache path: {cache.path}")


def apply_proposal(state: OntologyState, proposal: Proposal):
    return apply(state, proposal.ops)


for epoch in range(N_EPOCHS):
    print(f"--> Epoch {epoch}")
    for i in range(0, len(SAMPLES), BATCH_SIZE):
        print(f"---> Batch {i}")
        samples = SAMPLES[i : i + BATCH_SIZE]

        proposal = propose_changes(state=state, samples=samples, intent=INTENT)
        # TODO: try to apply proposal here. If it does not work, send it back.

        cache.write((f"e{epoch}", f"b{i}", "proposal.json"), proposal.model_dump_json(indent=2))

        # ranked_proposals = rank_proposals(proposals=proposals, state=state, intent=INTENT)
        # best_proposal = ranked_proposals[0]

        state = apply_proposal(state=state, proposal=proposal)
