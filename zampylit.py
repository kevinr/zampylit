#!/usr/bin/env python3

import os, sys, re, argparse
import arrow

if os.name == 'posix' and sys.version_info[0] < 3:
    import subprocess32 as subprocess
else:
    import subprocess

def main():
    wdir = os.path.basename(os.getcwd())

    print wdir
    parser = argparse.ArgumentParser(description='A tool for measuring progress on group writing projects')
    parser.add_argument('--game-name', '-g', metavar='GAMENAME', default=wdir, help="the game's name (default: %(default)s)")
    parser.add_argument('--output-file', '-o', metavar='FILE', default=(wdir+'-wc'), help="prefix of the files to output (default: %(default)s)")
    parser.add_argument('--extensions', '-e', metavar='EXT', default='.tex,.txt', help="extensions of files whose words to count (default: %(default)s)")
    parser.add_argument('--namefold', '-n', metavar='FILE', help="file containing name mappings")
    args = parser.parse_args()

    gitlog = subprocess.check_output(['git', 'log'], universal_newlines=True)

    changelog_entry_re = re.compile(r'''
        ^commit\ (?P<commit>[0-9A-Fa-f]{40})\n
        Author:\ (?P<author>[^<]*) <(?P<email>[^>]*)>\n
        Date:\ \ \ (?P<date>[^\n]*)''', re.MULTILINE | re.VERBOSE)

    #parse the changelog
    changelog_entries = []
    for e in changelog_entry_re.finditer(gitlog):
        commit = e.group('commit')
        author = e.group('author').strip()
        date = arrow.get(e.group('date'), 'ddd MMM D HH:mm:ss YYYY Z')
        changelog_entries.append({'commit': commit, 'author': author, 'date': date})
        
    exts = ' -o '.join(['-name \*%s' % (x.strip(),) for x in args.extensions.split(',')])
    cmd = 'find . -type f \( %s \) -print0 | xargs -0 wc -w | tail -1 | grep -o "[0-9]\+"' % (exts,)

    running_total = 0
    running_totals_by_author = {}
    datapoints = []

    # walk through the history collecting wordcount changes by author
    for e in reversed(changelog_entries):
        subprocess.check_call(['git', 'checkout', e['commit']])
        try:
            wc = int(subprocess.check_output(cmd, shell=True))
        except subprocess.CalledProcessError as ex:
            sys.stderr.write(str(ex))
            wc = 0

        if e['author'] not in running_totals_by_author:
            running_totals_by_author[e['author']] = 0
        running_totals_by_author[e['author']] += (wc - running_total)

        d = {'author': e['author'], 'date': e['date'], 'words': running_totals_by_author[e['author']]}
        datapoints.append(d)
        print(d)

        running_total = int(wc)

    out = open(args.output_file+'.gnuplot', 'w')
    out.write('set xdata time\n')
    out.write('set timefmt "%s"\n')
    out.write('set format x "%m/%d"\n')
    out.write('set terminal pdf size 10in,7.5in\n')
    out.write('set output "%s.pdf"\n' % (args.output_file,))
    out.write('set xlabel "date"\n')
    out.write('set ylabel "words"\n')
    out.write('set title "%s word counts by author"\n' % (args.game_name,))
    out.write('set datafile missing "?"\n')
    out.write('plot ' + ', '.join(['"%s.data" using 1:($%d) title "%s"' % (args.output_file, i, author) for i, author in enumerate(running_totals_by_author.keys(), 2)]) + '\n')
    out.close()

    data = open(args.output_file+'.data', 'w')
    for d in datapoints:
        print(d)
        data.write('\t'.join([str(d['date'].timestamp)] + [str(d['words']) if d['author'] == a else '?' for a in running_totals_by_author.keys()]) + '\n')
    data.close()

    subprocess.check_call(['gnuplot', args.output_file+'.gnuplot'])

if __name__=='__main__': main()
