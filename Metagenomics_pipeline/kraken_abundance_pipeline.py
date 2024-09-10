import os
import pandas as pd
import random
from collections import defaultdict
import plotly.express as px
import plotly.io as pio
from .trimmomatic import run_trimmomatic
from .bowtie2 import run_bowtie2
from .kraken2 import run_kraken2

# Ensure Kaleido is used for static image export
pio.kaleido.scope.default_format = "png"

def process_sample(forward, reverse, base_name, bowtie2_index, kraken_db, output_dir, threads, run_bowtie, use_precomputed_reports):
    if not use_precomputed_reports:
        # Step 1: Run Trimmomatic (only if not using precomputed reports)
        trimmed_forward, trimmed_reverse = run_trimmomatic(forward, reverse, base_name, output_dir, threads)

        # Step 2: Optionally Run Bowtie2 to deplete host genome reads
        if run_bowtie:
            unmapped_r1, unmapped_r2 = run_bowtie2(trimmed_forward, trimmed_reverse, base_name, bowtie2_index, output_dir, threads)
        else:
            unmapped_r1, unmapped_r2 = trimmed_forward, trimmed_reverse

        # Step 3: Use the reads as input for Kraken2
        kraken_report = run_kraken2(unmapped_r1, unmapped_r2, base_name, kraken_db, output_dir, threads)
    else:
        # Use the precomputed Kraken2 report
        kraken_report = os.path.join(output_dir, f"{base_name}_report.txt")
        if not os.path.exists(kraken_report):
            raise FileNotFoundError(f"Precomputed Kraken2 report not found: {kraken_report}")

    return kraken_report

def aggregate_kraken_results(kraken_dir, metadata_file, read_count):
    metadata = pd.read_csv(metadata_file, sep=",")
    sample_id_col = metadata.columns[0]  # Assume the first column is the sample ID

    # Dictionary to store aggregated results
    aggregated_results = {}

    # Iterate over each Kraken report file
    for file_name in os.listdir(kraken_dir):
        if file_name.endswith("_report.txt"):
            with open(os.path.join(kraken_dir, file_name), 'r') as f:
                for line in f:
                    fields = line.strip().split('\t')
                    perc_frag_cover = fields[0]
                    nr_frag_cover = fields[1]
                    nr_frag_direct_at_taxon = int(fields[2])
                    rank_code = fields[3]
                    ncbi_ID = fields[4]
                    scientific_name = fields[5]
                    parts = file_name.split('_')
                    extracted_part = '_'.join(parts[:-1])
                    sampleandtaxonid = extracted_part + str(ncbi_ID)

                    if rank_code == 'S' and nr_frag_direct_at_taxon >= read_count:
                        if extracted_part in metadata[sample_id_col].unique():
                            sample_metadata = metadata.loc[metadata[sample_id_col] == extracted_part].iloc[0].to_dict()
                            aggregated_results[sampleandtaxonid] = {
                                'Perc_frag_cover': perc_frag_cover,
                                'Nr_frag_cover': nr_frag_cover,
                                'Nr_frag_direct_at_taxon': nr_frag_direct_at_taxon,
                                'Rank_code': rank_code,
                                'NCBI_ID': ncbi_ID,
                                'Scientific_name': scientific_name,
                                'SampleID': extracted_part,
                                **sample_metadata
                            }

    # Output aggregated results to a TSV file
    merged_tsv_path = os.path.join(kraken_dir, "merged_kraken1.tsv")
    with open(merged_tsv_path, 'w') as f:
        # Write headers dynamically
        headers = ['Perc_frag_cover', 'Nr_frag_cover', 'Nr_frag_direct_at_taxon', 'Rank_code', 'NCBI_ID', 'Scientific_name', 'SampleID'] + metadata.columns[1:].tolist()
        f.write("\t".join(headers) + "\n")
        for sampleandtaxonid, data in aggregated_results.items():
            f.write("\t".join(str(data[col]) for col in headers) + "\n")

    return merged_tsv_path

def generate_abundance_plots(merged_tsv_path, top_N):
    df = pd.read_csv(merged_tsv_path, sep="\t")
    df.columns = df.columns.str.replace('/', '_').str.replace(' ', '_')
    df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))
    df = df[df['Scientific_name'] != 'Homo sapiens']

    # Generate both viral and bacterial abundance plots
    for focus, filter_str, plot_title in [
        ('Virus_Type', 'Virus', 'Viral'),
        ('Bacteria_Type', 'Virus', 'Bacterial')
    ]:
        if focus == 'Bacteria_Type':
            df_focus = df[~df['Scientific_name'].str.contains(filter_str, case=False, na=False)]
        else:
            df_focus = df[df['Scientific_name'].str.contains(filter_str, case=False, na=False)]
        df_focus = df_focus.rename(columns={'Scientific_name': focus})

        if top_N:
            top_N_categories = df_focus[focus].value_counts().head(top_N).index
            df_focus = df_focus[df_focus[focus].isin(top_N_categories)]

        categorical_cols = df_focus.select_dtypes(include=['object']).columns.tolist()
        categorical_cols.remove(focus)

        for col in categorical_cols:
            grouped_sum = df_focus.groupby([focus, col])['Nr_frag_direct_at_taxon'].mean().reset_index()

            colordict = defaultdict(int)
            random_colors = ["#{:06x}".format(random.randint(0, 0xFFFFFF)) for _ in range(len(grouped_sum[col].unique()))]
            for target, color in zip(grouped_sum[focus].unique(), random_colors):
                colordict[target] = color

            plot_width = 1100 + 5 * len(grouped_sum[col].unique())
            plot_height = 800 + 5 * len(grouped_sum[col].unique())
            font_size = max(10, 14 - len(grouped_sum[col].unique()) // 10)

            fig = px.bar(
                grouped_sum,
                x=col,
                y='Nr_frag_direct_at_taxon',
                color=focus,
                color_discrete_map=colordict,
                title=f"{plot_title} Abundance by {col}"
            )

            fig.update_layout(
                xaxis=dict(tickfont=dict(size=font_size), tickangle=45),
                yaxis=dict(tickfont=dict(size=font_size)),
                title=dict(text=f'Average {plot_title} Abundance by {col}', x=0.5, font=dict(size=16)),
                bargap=0.5,
                legend=dict(
                    font=dict(size=font_size),
                    x=1,
                    y=1,
                    traceorder='normal',
                    orientation='v',
                    itemwidth=30,
                    itemsizing='constant',
                    itemclick='toggleothers',
                    itemdoubleclick='toggle'
                ),
                width=plot_width,
                height=plot_height
            )

            output_path = f"{plot_title}_Abundance_by_{col}.png"
            fig.write_image(output_path, format='png', scale=3)

            print(f"Figure saved as {output_path}")

# Main script to run the pipeline
if __name__ == "__main__":
    import sys
    import os
    import argparse
    import glob
    sys.path.append(os.getcwd())
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

        for forward in glob.glob(os.path.join(args.input_dir, "*_R1.fastq*")):
            base_name = os.path.basename(forward).replace("_R1.fastq.gz", "").replace("_R1.fastq", "")
            reverse = forward.replace("_R1.fastq", "_R2.fastq").replace("_R1.fastq.gz", "_R2.fastq.gz")

            process_sample(forward, reverse, base_name, args.bowtie2_index, args.kraken_db, args.output_dir, args.threads, run_bowtie, args.use_precomputed_reports)

        merged_tsv_path = aggregate_kraken_results(args.output_dir, args.metadata_file, args.read_count)

        if args.bacteria or args.virus:
            generate_abundance_plots(merged_tsv_path, args.top_N)

    main()
