import sys

from ontology_hydra.cli.args import parse_args
from ontology_hydra.cli.commands import generate_ontology as generate_ontology_cmd
from ontology_hydra.cli.commands import init as init_cmd
from ontology_hydra.cli.logging import configure_logging


def main():
    configure_logging()
    res = parse_args(sys.argv[1:])

    match res:
        case ("init", args):
            init_cmd.init(args)
            return

        case ("generate-ontology", args):
            generate_ontology_cmd.generate_ontology(args)
            return
