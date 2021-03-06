import json

from iggtools.common.argparser import add_subcommand
from iggtools.common.utils import tsprint, InputStream, num_physical_cores, command, select_from_tsv
from iggtools.common.bowtie2 import build_bowtie2_db, bowtie2_index_exists
from iggtools.models.uhgg import MIDAS_IGGDB


def register_args(main_func):
    subparser = add_subcommand('build_bowtie2_indexes', main_func, help='build repgenome and pangenome bowtie2 indexes given list of species')

    subparser.add_argument('--midas_iggdb',
                           dest='midas_iggdb',
                           type=str,
                           metavar="CHAR",
                           required=True,
                           help=f"Local MIDAS DB which mirrors the s3 IGG db")
    subparser.add_argument('--bt2_indexes_dir',
                           dest='bt2_indexes_dir',
                           type=str,
                           metavar="CHAR",
                           required=True,
                           help=f"Path to bowtie2 indexes directory")
    subparser.add_argument('--bt2_indexes_name',
                           dest='bt2_indexes_name',
                           type=str,
                           metavar="CHAR",
                           default="repgenomes",
                           choices=['repgenomes', 'pangenomes'],
                           help=f"Bowtie2 db name to build")

    subparser.add_argument('--species_csv',
                           dest='species_csv',
                           type=str,
                           metavar="CHAR",
                           help=f"Comma separated species ids")
    subparser.add_argument('--species_list',
                           dest='species_list',
                           type=str,
                           metavar="CHAR",
                           help=f"Comma separated list of species ids")
    subparser.add_argument('--species_profile',
                           dest='species_profile',
                           type=str,
                           metavar="CHAR",
                           help=f"Path to species coverage TSV file with species_id")
    subparser.add_argument('--select_by',
                           dest='select_by',
                           type=str,
                           metavar="CHAR",
                           default="sample_counts",
                           help=f"Column from species_profile based on which to select species.")
    subparser.add_argument('--select_threshold',
                           dest='select_threshold',
                           type=float,
                           metavar="FLOAT",
                           help=f"Minimum threshold values of for selected columns.")

    subparser.add_argument('--num_cores',
                           dest='num_cores',
                           type=int,
                           metavar="INT",
                           default=num_physical_cores,
                           help=f"Number of physical cores to use ({num_physical_cores})")
    return main_func


def build_bowtie2_indexes(args):

    try:
        # comman-separated species ids
        if args.species_csv:
            species_ids_of_interest = args.species_csv.split(",")
        # one species per line
        elif args.species_list:
            species_ids_of_interest = []
            with InputStream(args.species_list) as stream:
                for species_id in select_from_tsv(stream, schema={"species_id": str}):
                    species_ids_of_interest.append(species_id[0])
        # this part is under development
        elif args.species_profile and args.select_by and args.select_threshold:
            species_ids_of_interest = []
            with InputStream(args.species_profile) as stream:
                for row in select_from_tsv(stream, selected_columns=["species_id", args.select_by], result_structure=dict):
                    if float(row[args.select_by]) >= args.select_threshold:
                        species_ids_of_interest.append(row["species_id"])
        else:
            raise Exception(f"Need to provide either species_list or species_profile as input arguments")
        tsprint(f"CZ::build_bowtie2_indexes::build bt2 indexees for the listed species: {species_ids_of_interest}")


        # Fetch UHGG related files
        midas_iggdb = MIDAS_IGGDB(args.midas_iggdb, args.num_cores)

        if args.bt2_indexes_name == "repgenomes":
            tsprint(f"CZ::build_bowtie2_repgenomes_indexes::start")
            contigs_files = midas_iggdb.fetch_files("prokka_genome", species_ids_of_interest)
            tsprint(contigs_files)
            build_bowtie2_db(args.bt2_indexes_dir, args.bt2_indexes_name, contigs_files, args.num_cores)
            tsprint(f"CZ::build_bowtie2_repgenomes_indexes::finish")

        if args.bt2_indexes_name == "pangenomes":
            tsprint(f"CZ::build_bowtie2_pangenomes_indexes::start")
            centroids_files = midas_iggdb.fetch_files("marker_centroids", species_ids_of_interest)
            tsprint(centroids_files)
            build_bowtie2_db(args.bt2_indexes_dir, args.bt2_indexes_name, centroids_files, args.num_cores)
            tsprint(f"CZ::build_bowtie2_pangenomes_indexes::finish")

    except Exception as error:
        if not args.debug:
            tsprint("Deleting untrustworthy outputs due to error. Specify --debug flag to keep.")
            command(f"rm -f {args.bt2_indexes_dir}")
        raise error


@register_args
def main(args):
    tsprint(f"Doing important work in subcommand {args.subcommand} with args\n{json.dumps(vars(args), indent=4)}")
    build_bowtie2_indexes(args)
