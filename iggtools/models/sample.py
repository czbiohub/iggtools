#!/usr/bin/env python3
import os
from iggtools.params.schemas import fetch_schema_by_dbtype
from iggtools.common.utils import InputStream, select_from_tsv, command, tsprint


# Executable Documentation
# Low level functions: the Target Files
def get_single_layout(sample_name, dbtype=""):
    def per_species(species_id="", chunk_id=""):
        return {
            "sample_dir":             f"{sample_name}",
            "outdir":                 f"{sample_name}/{dbtype}",
            "output_subdir":          f"{sample_name}/{dbtype}/{species_id}",

            "tempdir":                f"{sample_name}/temp/{dbtype}",
            "temp_subdir":            f"{sample_name}/temp/{dbtype}/{species_id}",

            "midas_iggdb_dir":        f"midas_iggdb",
            "bt2_indexes_dir":        f"{sample_name}/bt2_indexes/{dbtype}",

            # species workflow output
            "species_summary":        f"{sample_name}/species/species_profile.tsv",
            "species_alignments_m8":  f"{sample_name}/temp/species/alignments.m8",

            # snps workflow output
            "snps_summary":           f"{sample_name}/snps/snps_summary.tsv",
            "snps_pileup":            f"{sample_name}/snps/{species_id}.snps.tsv.lz4",
            "snps_repgenomes_bam":    f"{sample_name}/temp/snps/repgenomes.bam",
            "chunk_pileup":           f"{sample_name}/temp/snps/{species_id}/snps_{chunk_id}.tsv.lz4",

            # genes workflow output
            "genes_summary":          f"{sample_name}/genes/genes_summary.tsv",
            "genes_coverage":         f"{sample_name}/genes/{species_id}.genes.tsv.lz4",
            "genes_pangenomes_bam":   f"{sample_name}/temp/genes/pangenomes.bam",
            "chunk_coverage":         f"{sample_name}/temp/genes/{species_id}/genes_{chunk_id}.tsv.lz4"
        }
    return per_species


class Sample: # pylint: disable=too-few-public-methods
    def __init__(self, sample_name, midas_outdir, dbtype=None):
        self.sample_name = sample_name
        self.midas_outdir = midas_outdir
        self.layout = get_single_layout(sample_name, dbtype)


    def get_target_layout(self, filename, species_id="", chunk_id=""):
        if isinstance(self.layout(species_id, chunk_id)[filename], list):
            local_file_lists = self.layout(species_id, chunk_id)[filename]
            return [os.path.join(self.midas_outdir, fn) for fn in local_file_lists]
        return os.path.join(self.midas_outdir, self.layout(species_id, chunk_id)[filename])


    def create_dirs(self, list_of_dirnames, debug=False, quiet=False):
        for dirname in list_of_dirnames:
            if dirname == "outdir":
                tsprint(f"Create OUTPUT directory for {self.sample_name}.")
            if dirname == "tempdir":
                tsprint(f"Create TEMP directory for {self.sample_name}.")
            if dirname == "dbsdir":
                tsprint(f"Create DBS directory for {self.sample_name}.")
            _create_dir(self.get_target_layout(dirname), debug, quiet)


    def create_species_subdirs(self, species_ids, dirname, debug=False, quiet=False):
        for species_id in species_ids:
            species_subdir = self.get_target_layout(f"{dirname}_subdir", species_id)
            _create_dir(species_subdir, debug, quiet)


    def select_species(self, marker_depth, species_list=[]):
        """ Parse species_summary and return list of species for pileup/pangenome analysis """
        schema = fetch_schema_by_dbtype("species")
        species_ids = []

        assert os.path.exists(self.get_target_layout("species_summary")), f"Need run midas_run_species before midas_run_snps for {self.sample_name}"
        with InputStream(self.get_target_layout("species_summary")) as stream:
            for record in select_from_tsv(stream, selected_columns=schema, result_structure=dict):
                if len(species_list) > 0 and record["species_id"] not in species_list:
                    continue
                if record["coverage"] >= marker_depth:
                    species_ids.append(record["species_id"])
        return species_ids


    def load_profile_by_dbtype(self, dbtype):
        """ Load genes/snps summary in memory and used in Pool model """
        summary_path = self.get_target_layout(f"{dbtype}_summary")
        assert os.path.exists(summary_path), f"load_profile_by_dbtype:: missing {summary_path} for {self.sample_name}"

        schema = fetch_schema_by_dbtype(dbtype)
        profile = {}
        with InputStream(summary_path) as stream:
            for info in select_from_tsv(stream, selected_columns=schema, result_structure=dict):
                profile[info["species_id"]] = info
        self.profile = profile


    def remove_dirs(self, list_of_dirnames):
        for dirname in list_of_dirnames:
            dirpath = self.get_target_layout(dirname)
            command(f"rm -rf {dirpath}", check=False)


def _create_dir(dirname, debug, quiet=False):
    if debug and os.path.exists(dirname):
        tsprint(f"Use existing {dirname} according to --debug flag.")
    else:
        command(f"rm -rf {dirname}", quiet)
        command(f"mkdir -p {dirname}", quiet)
