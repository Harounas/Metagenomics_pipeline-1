import sys
import os
import argparse
import glob
import pandas as pd
from Metagenomics_pipeline.kraken_abundance_pipeline import process_sample, aggregate_kraken_results, generate_abundance_plots

def main():
    parser = argparse.ArgumentParser(description="Pipeline for Trimmomatic trimming, Bowtie2 host depletion (optional), and Kraken2 taxonomic classification.")
    parser.add_argument("--kraken_db", required=True, help="Path to Kraken2 database.")
    parser.add_argument("--bowtie2_index", help="Path to Bowtie2 index (optional).")
    parser.add_argument("--output_dir", required=True, help="Directory to save output files.")
    parser.add_argument("--input_dir", required=True, help="Directory containing input FASTQ files.")
    parser.add_argument("--threads", type=int, default=8, help="Number of threads to use for Trimmomatic, Bowtie2, and Kraken2.")
    parser.add_argument("--metadata_file", required=True, help="Path to the metadata CSV file.")
    parser.add_argument("--read_count", type=int, default=0, help="Minimum read count threshold.")
    parser.add_argument("--top_N", type=int, default=None, help="Select the top N most common viruses or bacteria.")
    parser.add_argument("--no_bowtie2", action='store_true', help="Skip Bowtie2 host depletion.")
    parser.add_argument("--bacteria", action='store_true', help="Generate bacterial abundance plots.")
    parser.add_argument("--virus", action='store_true', help="Generate viral abundance plots.")
    parser.add_argument("--use_precomputed_reports", action='store_true', help="Use precomputed Kraken reports instead of running Kraken2.")

    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    run_bowtie = not args.no_bowtie2 and args.bowtie2_index is not None

    # Step 1: Process each sample
    for forward in glob.glob(os.path.join(args.input_dir, "*_R1.fastq*")):
        base_name = os.path.basename(forward).replace("_R1.fastq.gz", "").replace("_R1.fastq", "")
        reverse = os.path.join(args.input_dir, f"{base_name}_R2.fastq.gz") if forward.endswith(".gz") else os.path.join(args.input_dir, f"{base_name}_R2.fastq")
        
        if not os.path.isfile(reverse):
            reverse = None

        # Process each sample and run Trimmomatic, Bowtie2, Kraken2
        process_sample(forward, reverse, base_name, args.bowtie2_index, args.kraken_db, args.output_dir, args.threads, run_bowtie, args.use_precomputed_reports)

    # Step 2: Aggregate Kraken results
    merged_tsv_path = aggregate_kraken_results(args.output_dir, args.metadata_file, args.read_count)
    print(f"Aggregated Kraken results saved to: {merged_tsv_path}")

    # Step 3: Generate both viral and bacterial abundance plots
    df = pd.read_csv(merged_tsv_path, sep="\t")
    print("Preview of aggregated Kraken results:")
    print(df.head())  # Preview the data before plotting

    # Step 4: Generate plots based on user input
    if args.bacteria or args.virus:
        generate_abundance_plots(merged_tsv_path, args.top_N)
    else:
        print("No --bacteria or --virus flag provided. No plots will be generated.")

if __name__ == "__main__":
    main()
