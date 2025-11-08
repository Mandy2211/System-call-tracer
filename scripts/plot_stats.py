#!/usr/bin/env python3
import sys
import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
from matplotlib.patches import Rectangle

class SystemThresholds:
    AVG_TIME_WARNING = 1_000_000
    AVG_TIME_CRITICAL = 10_000_000
    HIGH_FREQUENCY_THRESHOLD = 1000
    TOTAL_TIME_PCT_WARNING = 10.0
    TOTAL_TIME_PCT_CRITICAL = 25.0
    TIME_REGRESSION_WARNING = 20.0
    TIME_REGRESSION_CRITICAL = 50.0

COLORS = {
    'healthy': '#2ecc71',
    'warning': '#f39c12',
    'critical': '#e74c3c',
    'neutral': '#95a5a6'
}

def classify_health_status(value, warning_threshold, critical_threshold, inverse=False):
    if inverse:
        if value <= critical_threshold:
            return 'critical'
        elif value <= warning_threshold:
            return 'warning'
        else:
            return 'healthy'
    else:
        if value >= critical_threshold:
            return 'critical'
        elif value >= warning_threshold:
            return 'warning'
        else:
            return 'healthy'

def add_health_columns(df):
    df['time_health'] = df['avg_time_ns'].apply(                   
        lambda x: classify_health_status(x,                                        #passes x and calls classify health status function
                                         SystemThresholds.AVG_TIME_WARNING,
                                         SystemThresholds.AVG_TIME_CRITICAL)
    )
    
    total_time = df['total_time_ns'].sum()
    df['total_time_pct'] = (df['total_time_ns'] / total_time * 100) if total_time > 0 else 0
    
    df['bottleneck_health'] = df['total_time_pct'].apply(
        lambda x: classify_health_status(x,
                                         SystemThresholds.TOTAL_TIME_PCT_WARNING,
                                         SystemThresholds.TOTAL_TIME_PCT_CRITICAL)
    )
    
    df['risk_score'] = (
        (df['avg_time_ns'] / SystemThresholds.AVG_TIME_CRITICAL * 5).clip(0, 5) +
        (df['total_time_pct'] / SystemThresholds.TOTAL_TIME_PCT_CRITICAL * 5).clip(0, 5)
    )
    
    return df

def plot_with_thresholds(df, col, outname, topn=20, xlabel='', title='', warning_threshold=None, critical_threshold=None,
                         health_col=None):
    df2 = df.sort_values(col, ascending=False).head(topn).copy()
    df2 = df2[df2[col] > 0]
    
    if df2.empty:
        print(f"Skipping plot {outname} as there is no data to show.")
        return

    labels = df2['syscall']
    values = df2[col]
    
    if health_col and health_col in df2.columns:                  #dynamically assigning colours
        colors = df2[health_col].map(COLORS).fillna(COLORS['neutral'])
    else:
        colors = COLORS['neutral']
    
    fig, ax = plt.subplots(figsize=(14, 10)) 
    bars = ax.barh(labels, values, color=colors)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    if warning_threshold is not None:
        ax.axvline(warning_threshold, color=COLORS['warning'], 
                   linestyle='--', linewidth=2, alpha=0.7, label=f'Warning ({warning_threshold})')
    if critical_threshold is not None:
        ax.axvline(critical_threshold, color=COLORS['critical'], 
                   linestyle='--', linewidth=2, alpha=0.7, label=f'Critical ({critical_threshold})')
    
    if warning_threshold or critical_threshold:
        ax.legend(loc='lower right')
    
    for bar in bars:
        width = bar.get_width()
        if width > 0:
            label = f'{width:.2e}' if width > 1e6 else f'{width:.0f}'
            ax.text(width, bar.get_y() + bar.get_height()/2, f' {label}',
                    va='center', fontsize=9, color='black')
    
    plt.tight_layout()
    plt.savefig(outname, dpi=150, bbox_inches='tight')
    print(f"✓ Saved {outname}")
    plt.close()

def plot_health_dashboard(df, outname):
    df_top = df.nlargest(15, 'risk_score')
    
    if df_top.empty:
        print(f"Skipping health dashboard as there is insufficient data.")
        return
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('System Call Health Dashboard - Potential Overload Indicators', 
                 fontsize=16, fontweight='bold', y=1.02)
    
    ax = axes[0]
    df_time = df_top.sort_values('avg_time_ns', ascending=True)
    colors = df_time['time_health'].map(COLORS)
    bars = ax.barh(df_time['syscall'], df_time['avg_time_ns'] / 1_000_000, color=colors)
    ax.axvline(SystemThresholds.AVG_TIME_WARNING / 1_000_000, color=COLORS['warning'], 
               linestyle='--', linewidth=2, alpha=0.7, label='Warning')
    ax.axvline(SystemThresholds.AVG_TIME_CRITICAL / 1_000_000, color=COLORS['critical'], 
               linestyle='--', linewidth=2, alpha=0.7, label='Critical')
    ax.set_xlabel('Average Time (ms)', fontsize=10)
    ax.set_title('Average Execution Time Analysis', fontweight='bold')
    ax.legend(fontsize=8)
    
    ax = axes[1]
    df_bottleneck = df_top.sort_values('total_time_pct', ascending=True)
    colors = df_bottleneck['bottleneck_health'].map(COLORS)
    bars = ax.barh(df_bottleneck['syscall'], df_bottleneck['total_time_pct'], color=colors)
    ax.axvline(SystemThresholds.TOTAL_TIME_PCT_WARNING, color=COLORS['warning'], 
               linestyle='--', linewidth=2, alpha=0.7, label='Warning')
    ax.axvline(SystemThresholds.TOTAL_TIME_PCT_CRITICAL, color=COLORS['critical'], 
               linestyle='--', linewidth=2, alpha=0.7, label='Critical')
    ax.set_xlabel('% of Total Execution Time', fontsize=10)
    ax.set_title('Bottleneck Detection', fontweight='bold')
    ax.legend(fontsize=8)
    
    ax = axes[2]
    df_risk = df_top.sort_values('risk_score', ascending=True)
    risk_colors = []
    for score in df_risk['risk_score']:
        if score >= 7:
            risk_colors.append(COLORS['critical'])
        elif score >= 4:
            risk_colors.append(COLORS['warning'])
        else:
            risk_colors.append(COLORS['healthy'])
    
    bars = ax.barh(df_risk['syscall'], df_risk['risk_score'], color=risk_colors)
    ax.axvline(4, color=COLORS['warning'], linestyle='--', linewidth=2, alpha=0.7, label='Warning')
    ax.axvline(7, color=COLORS['critical'], linestyle='--', linewidth=2, alpha=0.7, label='Critical')
    ax.set_xlabel('Composite Risk Score (0-10)', fontsize=10)
    ax.set_title('Overall System Overload Risk', fontweight='bold')
    ax.legend(fontsize=8)
    
    plt.tight_layout()
    plt.savefig(outname, dpi=150, bbox_inches='tight')
    print(f"✓ Saved {outname}")
    plt.close()

def generate_alert_report(df, outfile):
    critical_issues = []
    warning_issues = []
    
    for _, row in df.iterrows():
        syscall = row['syscall']
        issues = []
        
        if row['avg_time_ns'] >= SystemThresholds.AVG_TIME_CRITICAL:
            issues.append(f"CRITICAL: Avg time {row['avg_time_ns']/1_000_000:.2f}ms (threshold: {SystemThresholds.AVG_TIME_CRITICAL/1_000_000:.2f}ms)")
        elif row['avg_time_ns'] >= SystemThresholds.AVG_TIME_WARNING:
            issues.append(f"WARNING: Avg time {row['avg_time_ns']/1_000_000:.2f}ms (threshold: {SystemThresholds.AVG_TIME_WARNING/1_000_000:.2f}ms)")
        
        if row['total_time_pct'] >= SystemThresholds.TOTAL_TIME_PCT_CRITICAL:
            issues.append(f"CRITICAL: Consuming {row['total_time_pct']:.1f}% of total time (threshold: {SystemThresholds.TOTAL_TIME_PCT_CRITICAL:.1f}%)")
        elif row['total_time_pct'] >= SystemThresholds.TOTAL_TIME_PCT_WARNING:
            issues.append(f"WARNING: Consuming {row['total_time_pct']:.1f}% of total time (threshold: {SystemThresholds.TOTAL_TIME_PCT_WARNING:.1f}%)")
        
        if issues:
            entry = f"\n{syscall} (called {int(row['count'])} times):\n"
            for issue in issues:
                entry += f"  • {issue}\n"
            
            if any('CRITICAL' in i for i in issues):
                critical_issues.append(entry)
            else:
                warning_issues.append(entry)
    
    with open(outfile, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("SYSTEM CALL ANALYSIS - THRESHOLD ALERT REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        if critical_issues:
            f.write("CRITICAL ISSUES (Immediate Attention Required):\n")
            f.write("-" * 80 + "\n")
            for issue in critical_issues:
                f.write(issue)
        else:
            f.write("✓ No critical issues detected.\n\n")
        
        if warning_issues:
            f.write("\nWARNING ISSUES (Should Be Monitored):\n")
            f.write("-" * 80 + "\n")
            for issue in warning_issues:
                f.write(issue)
        else:
            f.write("\n✓ No warning-level issues detected.\n")
        
        if not critical_issues and not warning_issues:
            f.write("\n✓ All syscalls are operating within healthy thresholds.\n")
    
    print(f"✓ Saved {outfile}")

def analyze_single_file(filepath):
    print(f"\n{'='*80}")
    print(f"ANALYZING: {filepath}")
    print(f"{'='*80}\n")
    
    df = pd.read_csv(filepath)
    
    numeric_cols = ['total_time_ns', 'count', 'avg_time_ns', 'errors']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df = add_health_columns(df)
    
    outdir = os.path.splitext(filepath)[0] + "_threshold_analysis"
    os.makedirs(outdir, exist_ok=True)
    print(f"Output directory: {outdir}/\n")
    
    plot_with_thresholds(
        df, 'avg_time_ns', f'{outdir}/1_avg_time_with_thresholds.png',
        xlabel='Average Execution Time (ns)',
        title='Average Execution Time - Performance Check',
        warning_threshold=SystemThresholds.AVG_TIME_WARNING,
        critical_threshold=SystemThresholds.AVG_TIME_CRITICAL,
        health_col='time_health'
    )
    
    plot_with_thresholds(
        df, 'total_time_pct', f'{outdir}/2_total_time_pct_with_thresholds.png',
        xlabel='Percentage of Total Execution Time (%)',
        title='Total Time Percentage - Bottleneck Detection',
        warning_threshold=SystemThresholds.TOTAL_TIME_PCT_WARNING,
        critical_threshold=SystemThresholds.TOTAL_TIME_PCT_CRITICAL,
        health_col='bottleneck_health'
    )
    
    plot_with_thresholds(
        df, 'count', f'{outdir}/3_call_frequency.png',
        xlabel='Number of Calls',
        title='Call Frequency Analysis',
        health_col=None
    )
    
    plot_health_dashboard(df, f'{outdir}/4_health_dashboard.png')
    
    generate_alert_report(df, f'{outdir}/alert_report.txt')
    
    print(f"\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")
    print(f"Total syscalls analyzed: {len(df)}")
    print(f"Critical issues: {len(df[df['risk_score'] >= 7])}")
    print(f"Warning issues: {len(df[(df['risk_score'] >= 4) & (df['risk_score'] < 7)])}")
    print(f"Healthy syscalls: {len(df[df['risk_score'] < 4])}")
    print(f"\nHighest risk syscalls:")
    for _, row in df.nlargest(5, 'risk_score').iterrows():
        print(f"  • {row['syscall']}: Risk Score {row['risk_score']:.2f}")
    print(f"\n{'='*80}\n")

def plot_comparison_with_thresholds(df, col, outname, xlabel='', title='', 
                                    warning_threshold=None, critical_threshold=None):
    df2 = df.reindex(df[col].abs().sort_values(ascending=False).index).head(20)
    df2 = df2.sort_values(col, ascending=True)
    
    if df2.empty or df2[col].abs().sum() == 0:
        print(f"Skipping plot {outname} as there are no changes to show.")
        return
    
    labels = df2['syscall']
    values = df2[col]
    
    colors = []
    for v in values:
        if v < 0:
            colors.append(COLORS['healthy'])
        elif warning_threshold and critical_threshold:
            if v >= critical_threshold:
                colors.append(COLORS['critical'])
            elif v >= warning_threshold:
                colors.append(COLORS['warning'])
            else:
                colors.append(COLORS['neutral'])
        else:
            colors.append(COLORS['critical'] if v > 0 else COLORS['healthy'])
    
    fig, ax = plt.subplots(figsize=(14, 10))
    bars = ax.barh(labels, values, color=colors)
    ax.axvline(0, color='grey', linewidth=1.5, linestyle='-', alpha=0.8)
    
    if warning_threshold is not None:
        ax.axvline(warning_threshold, color=COLORS['warning'], 
                   linestyle='--', linewidth=2, alpha=0.7, label=f'Warning (+{warning_threshold}%)')
    if critical_threshold is not None:
        ax.axvline(critical_threshold, color=COLORS['critical'], 
                   linestyle='--', linewidth=2, alpha=0.7, label=f'Critical (+{critical_threshold}%)')
    
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=20)
    
    if warning_threshold or critical_threshold:
        ax.legend(loc='best')
    
    plt.tight_layout()
    plt.savefig(outname, dpi=150, bbox_inches='tight')
    print(f"✓ Saved {outname}")
    plt.close()

def analyze_comparison(file_before, file_after):
    print(f"\n{'='*80}")
    print(f"COMPARING: '{file_before}' (BEFORE) vs '{file_after}' (AFTER)")
    print(f"{'='*80}\n")
    
    df_before = pd.read_csv(file_before)
    df_after = pd.read_csv(file_after)
    
    df = pd.merge(df_before, df_after, on='syscall', suffixes=('_before', '_after'), how='outer')
    df.fillna(0, inplace=True)
    
    df['time_delta_ns'] = df['total_time_ns_after'] - df['total_time_ns_before']
    df['count_delta'] = df['count_after'] - df['count_before']
    
    df['time_pct_change'] = np.where(
        df['total_time_ns_before'] > 0,
        100 * (df['time_delta_ns'] / df['total_time_ns_before']),
        0
    )
    
    outdir = f"comparison_{os.path.basename(os.path.splitext(file_before)[0])}_vs_{os.path.basename(os.path.splitext(file_after)[0])}"
    os.makedirs(outdir, exist_ok=True)
    print(f"Output directory: {outdir}/\n")
    
    plot_comparison_with_thresholds(
        df, 'time_pct_change', f'{outdir}/1_time_regression_analysis.png',
        xlabel='Change in Total Time (%) [Green=Improvement, Red=Regression]',
        title='Performance Regression Analysis with Thresholds',
        warning_threshold=SystemThresholds.TIME_REGRESSION_WARNING,
        critical_threshold=SystemThresholds.TIME_REGRESSION_CRITICAL
    )
    
    plot_comparison_with_thresholds(
        df, 'time_delta_ns', f'{outdir}/2_absolute_time_change.png',
        xlabel='Absolute Change in Total Time (ns)',
        title='Absolute Time Changes'
    )
    
    plot_comparison_with_thresholds(
        df, 'count_delta', f'{outdir}/3_call_frequency_change.png',
        xlabel='Change in Call Count',
        title='Call Frequency Changes'
    )
    
    regressions = df[df['time_pct_change'] >= SystemThresholds.TIME_REGRESSION_WARNING]
    with open(f'{outdir}/regression_report.txt', 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("PERFORMANCE REGRESSION REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        if len(regressions) > 0:
            f.write(f"Found {len(regressions)} syscalls with performance regressions:\n\n")
            for _, row in regressions.sort_values('time_pct_change', ascending=False).iterrows():
                severity = 'CRITICAL' if row['time_pct_change'] >= SystemThresholds.TIME_REGRESSION_CRITICAL else 'WARNING'
                f.write(f"{severity}: {row['syscall']}\n")
                f.write(f"  Time change: +{row['time_pct_change']:.1f}%\n")
                f.write(f"  Absolute change: +{row['time_delta_ns']:,.0f} ns\n")
                f.write(f"  Call frequency change: {row['count_delta']:+.0f}\n\n")
        else:
            f.write("✓ No significant performance regressions detected.\n")
    
    print(f"✓ Saved {outdir}/regression_report.txt")
    print(f"\n{'='*80}\n")

def main():
    print("\n" + "=" * 80)
    print("SYSCALL ANALYSIS TOOL - Enhanced with Threshold Detection")
    print("=" * 80)
    
    if len(sys.argv) == 2:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f" Error: File not found '{filepath}'")
            return
        analyze_single_file(filepath)
        
    elif len(sys.argv) == 3:
        file_before, file_after = sys.argv[1], sys.argv[2]
        if not os.path.exists(file_before):
            print(f" Error: File not found '{file_before}'")
            return
        if not os.path.exists(file_after):
            print(f" Error: File not found '{file_after}'")
            return
        analyze_comparison(file_before, file_after)
    else:
        print("\nUsage:")
        print("  Single file analysis: python plot_stats.py <path_to_syscalls.csv>")
        print("  Comparison analysis:  python plot_stats.py <before.csv> <after.csv>")
        print("\nThreshold Configuration:")
        print(f"  Avg Time - Warning: {SystemThresholds.AVG_TIME_WARNING/1_000_000:.1f}ms, Critical: {SystemThresholds.AVG_TIME_CRITICAL/1_000_000:.1f}ms")
        print(f"  Time % - Warning: {SystemThresholds.TOTAL_TIME_PCT_WARNING:.1f}%, Critical: {SystemThresholds.TOTAL_TIME_PCT_CRITICAL:.1f}%")
        print(f"  Regression - Warning: +{SystemThresholds.TIME_REGRESSION_WARNING:.0f}%, Critical: +{SystemThresholds.TIME_REGRESSION_CRITICAL:.0f}%")
        print()

if __name__ == "__main__":
    main()
