#!/usr/bin/env python3
# scripts/plot_stats.py
import sys
import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_top(df, col, outname, topn=15, horizontal=False, xlabel=''):
    df2 = df.sort_values(col, ascending=False).head(topn).copy()
    labels = df2['syscall']
    values = df2[col]
    plt.figure(figsize=(10,6))
    if horizontal:
        plt.barh(labels, values)
        plt.gca().invert_yaxis()
        plt.xlabel(xlabel)
    else:
        plt.bar(labels, values)
        plt.xticks(rotation=45, ha='right')
        plt.ylabel(xlabel)
    plt.title(f"Top {topn} by {col}")
    plt.tight_layout()
    plt.savefig(outname)
    print("Saved", outname)
    plt.close()

def main(csv_path):
    if not os.path.exists(csv_path):
        print("CSV file not found:", csv_path)
        return
    df = pd.read_csv(csv_path)
    # convert numeric columns if needed
    df['total_time_ns'] = pd.to_numeric(df['total_time_ns'])
    df['count'] = pd.to_numeric(df['count'])
    # Top by call count
    plot_top(df, 'count', 'data/syscall_counts.png', topn=20, horizontal=True, xlabel='Count')
    # Top by total time
    plot_top(df, 'total_time_ns', 'data/syscall_total_time_ns.png', topn=20, horizontal=True, xlabel='Total time (ns)')
    # Top by average time
    df['avg_time_ns'] = pd.to_numeric(df['avg_time_ns'])
    plot_top(df, 'avg_time_ns', 'data/syscall_avg_time_ns.png', topn=20, horizontal=True, xlabel='Avg time (ns)')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: plot_stats.py data/syscalls.csv")
    else:
        main(sys.argv[1])

