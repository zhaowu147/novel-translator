# -*- coding: utf-8 -*-
"""Logging layer: record final audit results after review."""

import sys, io, os, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def log_review(trans_dir, report_file='review_report.json'):
    """Generate audit log from review report."""
    report_path = os.path.join(trans_dir, report_file)
    if not os.path.exists(report_path):
        print(f'Report not found: {report_path}', flush=True)
        return None

    with open(report_path, encoding='utf-8') as f:
        report = json.load(f)

    title = report.get('title', 'Unknown')
    total = report.get('total', 0)
    passed = report.get('passed', 0)
    failed = report.get('failed', 0)
    issues = report.get('issues', [])

    log_lines = []
    log_lines.append(f'Translation Audit Log')
    log_lines.append(f'Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    log_lines.append(f'Novel: {title}')
    log_lines.append(f'Total chapters: {total}')
    log_lines.append(f'Passed: {passed}')
    log_lines.append(f'Failed: {failed}')
    log_lines.append(f'Pass rate: {passed/total*100:.1f}%' if total > 0 else 'N/A')
    log_lines.append('')

    if issues:
        log_lines.append(f'Failed chapters ({len(issues)}):')
        for issue in issues:
            log_lines.append(f'  [{issue["reason"]}] {issue["file"]}')
            if issue.get('detail'):
                log_lines.append(f'    Detail: {issue["detail"]}')
        log_lines.append('')

        by_reason = {}
        for issue in issues:
            reason = issue['reason']
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(issue['file'])

        log_lines.append('Issues by type:')
        for reason, files in by_reason.items():
            log_lines.append(f'  {reason}: {len(files)} chapters')
        log_lines.append('')

    if failed > 0:
        log_lines.append('Action required:')
        log_lines.append(f'  - {failed} chapters need retranslation')

    log_text = '\n'.join(log_lines)

    log_path = os.path.join(trans_dir, 'audit_log.txt')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(log_text)

    structured = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'title': title,
        'total': total,
        'passed': passed,
        'failed': failed,
        'pass_rate': round(passed/total*100, 1) if total > 0 else 0,
        'issues': issues,
    }
    structured_path = os.path.join(trans_dir, 'audit_log.json')
    with open(structured_path, 'w', encoding='utf-8') as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)

    print(log_text, flush=True)
    print(flush=True)
    print(f'Log: {log_path}', flush=True)

    return structured


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('trans_dir', help='Translated novel directory')
    parser.add_argument('--report', default='review_report.json')
    args = parser.parse_args()
    log_review(args.trans_dir, args.report)
