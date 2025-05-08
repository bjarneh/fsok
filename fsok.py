#!/usr/bin/env python3
r"""
 fsok - searchable treeview

 usage: fsok - [OPTIONS] [DIR(S)]

 options:
     -h --help    : print this menu and exit
     -v --version : print version and exit
     -f --fzf     : use fzf to match files
     -e --editor  : edit program ($EDITOR || vim)
"""


import sys
import os
import time
import signal
import random
import re
import curses
import subprocess
import datetime
import getopt



#____________________________________________ GLOBALS


__version__ = 1.0


# Regular match or fzf to find files
fzf_match = False
# Flat files are standard
treeview = True
# Cache treeview of hits
treeview_levels = []
# Offset for each level
spacer = '  '
# The active file that opens in 'vim' if 'Return' is pressed.
active = 0 #
# What directory to use as root if none is given?
roots = ['src'] # PWD
# The root window, the only window to be frank
mainscreen = None
# The current search string
searchstr = []
# The files we found under the root(s)
files = []
# The files matching the current search
hits = []

# What directories should not be included
skipdirs = ['.git','.hg','__pycache__','flask_session']
# What files should not be included
skipfiles = ['.jtv_state','.jtvrc']
# Files open with this program
editor = os.environ.get("EDITOR") or 'vim'


# Readable color constants
FG_WHITE_BG_BLUE   = 2
FG_CYAN_BG_BLACK   = 3
FG_YELLOW_BG_BLACK = 4


def niceopt(argv, short_opts, long_opts):
    """ Allow long options which start with a single '-' sign"""
    for i, e in enumerate(argv):
        for opt in long_opts:
            if( e.startswith("-" + opt) or
              ( e.startswith("-" + opt[:-1]) and opt[-1] == "=") ):
                argv[i] = "-" + e
    return getopt.gnu_getopt(argv, short_opts, long_opts)



def store_state():
    """
    If a search string is present, write it to $PWD/.fsok_state.txt
    and read it back next time we start the program, otherwise
    remove that file.
    """
    global searchstr
    try:
        pwd = os.getcwd()
        state_file = os.path.join(pwd, ".fsok.state.txt")
        if len(searchstr) == 0:
            if os.path.isfile(state_file):
                easylog("removing state_file: {}".format(state_file))
                os.remove(state_file)
        else:
            easylog("writing state {}, to state_file: {}".format(''.join(searchstr), state_file))
            with open(state_file,'w') as f:
                f.write(''.join(searchstr))
    except Exception as inst:
        pass


def restore_state():
    """
    If the file $PWD/.fsok_state.txt is present, read searchstr from it
    """
    global searchstr
    easylog("called: restore_state()")
    try:
        pwd = os.getcwd()
        state_file = os.path.join(pwd, ".fsok.state.txt")
        if os.path.isfile(state_file):
            with open(state_file,'r') as f:
                content = f.read().strip()
                easylog("read state {}, from state_file: {}".format(content, state_file))
                if content:
                    searchstr = list(content)
                    search_files()
    except Exception as inst:
        pass


def quit_peacefully(*args):
    """
    Reset terminal and exit. We need arguments
    only for the 'signal.signal' Ctrl+C trap that sends
    actual signal to function when Ctrl+C is pressed.
    Not used for anything here...
    """
    store_state()
    curses.nocbreak()
    curses.echo()
    curses.endwin()
    sys.exit()


def init_curses_screen():
    """
    Initialize main screen + curses with colors
    """
    scrn = curses.initscr();

    curses.setupterm()
    curses.cbreak();
    curses.noecho();
    curses.curs_set(0)
    #curses.use_default_colors()

    curses.start_color();
    # init color here..
    curses.init_pair(FG_WHITE_BG_BLUE, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(FG_CYAN_BG_BLACK, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(FG_YELLOW_BG_BLACK, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    scrn.bkgd(' ', curses.color_pair(FG_YELLOW_BG_BLACK))

    scrn.keypad(True) # map input to variable names (KEY_LEFT etc).
    scrn.clear();
    scrn.refresh()
    return scrn;


def bind_ctrlc_etc():
    """
    Bind Ctrl+C to a peaceful exit
    """
    signal.signal(signal.SIGINT , quit_peacefully)  #ctrl-c


def search_files():
    """
    Filter out files matching search string
    """
    global searchstr
    global files
    global active
    global hits

    # All visible on empty search
    if not searchstr:
        hits = files
    else:
        if fzf_match:
            hits = fzf_search()
        else:
            hits = []
            tok = ''.join(searchstr)
            multi_search = False
            toks = tok.split('|')
            if '|' in tok:
                multi_search = True
            for f in files:
                if multi_search:
                    for t in toks:
                        if t in f:
                            hits.append(f)
                            break;
                else:
                    if tok in f:
                        hits.append(f)
    if hits:
        active = 0
    else:
        active = -1
    create_levels()



def fzf_search():
    """
    Use 'fzf' to find matching files
    """
    global searchstr
    global files

    list_files_ps = subprocess.Popen(["echo", "-e", "\n".join(files)],
                                     stdout=subprocess.PIPE, text=True)
    grep_process = subprocess.Popen(["fzf", "--filter", ''.join(searchstr)],
                        stdin=list_files_ps.stdout,
                        stdout=subprocess.PIPE, text=True)

    output, error = grep_process.communicate()
    grepped_files = output.strip().split('\n')
    return grepped_files



def move_active(up):
    """ Move active selection"""
    global active
    if up:
        if active > 0:
            active -= 1
    else: # down
        if treeview:
            if treeview_levels:
                ( level, line, name ) = treeview_levels[-1]
                if active < line[0]:
                    active += 1
        else:
            if active+1 < len(hits):
                active += 1


def open_file():
    """
    Open editor (vim) with active file
    """

    global active
    global hits
    global mainscreen
    global editor

    if active >= 0:
        cmd = [editor, hits[active]]
        easylog(cmd)
        fail = subprocess.call(cmd)
        if fail:
            easylog("open: {}, failed for some reason".format(hits[active]))
        # Hmm :-)
        mainscreen.keypad(True)
    else:
        easylog("!open file {}".format(active))

    mainscreen.refresh()
    mainscreen.clear();


def reload_tree():
    """
    Reload treeview, to see new files etc.
    """
    global treeview_levels
    #global active = 0 #
    global files
    #active
    treeview_levels = []
    files = []
    #hits = []
    find_files()


def mainloop():
    """
    Constant loop, as long as the program runs
    """
    global searchstr
    global mainscreen
    global treeview
    global fzf_match

    # from state
    search_files()

    while True:
        
        drawscreen()
        dosearch = True

        ch = mainscreen.getch()
        easylog("getch(): {}".format(ch))

        # Delete last character
        if ch == curses.KEY_BACKSPACE and searchstr:
            searchstr = searchstr[:-1]
        elif ch == curses.KEY_RESIZE:
            mainscreen.refresh()
            mainscreen.clear();
            dosearch = False
        # Ctrl+ R => Reverse sort files
        elif ch == 18:
            files.reverse()
        # Ctrl + Backspace => Delete entire search
        elif ch == 8:
            searchstr = []
        elif ch == 10: # Return
            if ''.join(searchstr) in [':q',':q!',':exit','exit()']:
                break
            else:
                dosearch = False
                open_file()
        elif ch == 20: # Ctrl + T
            treeview = not treeview
            dosearch = False
        elif ch == 11: # Ctrl + U
            fzf_match = not fzf_match
            dosearch = True
        elif ch > 255:
            dosearch = False
            if ch == curses.KEY_UP:
                move_active(True)
            elif ch == curses.KEY_DOWN:
                move_active(False)
            elif ch == curses.KEY_F5:
                dosearch = True
                reload_tree()
            # Clear on Return + Backspace
            elif ch == 330:
                searchstr = []
        elif ch < 255:
            ok = chr(ch) 
            if ok.isprintable():
                searchstr += ok
            else:
                dosearch = False

        if dosearch:
            search_files()


def easylog(msg):
    """ Log like a man!"""
    logfile = os.path.join( os.path.expanduser("~"), ".fsok.log")
    with open(logfile,'a') as f:
        f.write("[{}] {}\n".format(datetime.datetime.now(), msg))


def drawscreen():
    """
    Draw search header + files + footer
    """
    global files
    global hits
    global active
    global mainscreen
    global treeview
    global treeview_levels
    global spacer
    global fzf_match

    #icon = "✈"
    icon = ">"

    match_type = "[reg]"
    if fzf_match:
        match_type = "[fzf]"

    # how many lines have we drawn in the top area
    visible = 0

    lines, cols = mainscreen.getmaxyx()
    mainscreen.addstr(0, 0, ("{} - {} x {} ".format(match_type, lines, cols)).rjust(cols), curses.color_pair(3))

    if not treeview: # flat view, list mathces as file-paths

        if hits:
            c = 0
            last_fline = lines-3
            # draw flat matches
            for f in hits:
                text = f
                if c > 0: text = f.ljust(cols)
                if c < last_fline:
                    visible += 1
                    if c == active:
                        mainscreen.addstr(c, 0, text, curses.A_BOLD|curses.color_pair(FG_YELLOW_BG_BLACK))
                    else:
                        mainscreen.addstr(c, 0, text, curses.color_pair(FG_YELLOW_BG_BLACK))
                    c += 1
                else:
                    if len(hits) > last_fline:
                        visible += 1
                        mainscreen.addstr(last_fline, 0, "+ {} more matches".format(
                            len(hits)-last_fline), curses.color_pair(FG_CYAN_BG_BLACK))
                    break

    else: # treeview of matches, with a filtered treeview

        if treeview_levels:
            drawn = []
            c = 0
            last_fline = lines-3
            # draw flat matches
            for f in treeview_levels:
                ( level, line, name ) = f
                if c < last_fline:
                    visible += 1
                    text = "{}{}".format(level * spacer, name)
                    if c > 0: text = text.ljust(cols)
                    if active in line:
                        drawn.append(c)
                        mainscreen.addstr(c, 0, text, curses.A_BOLD|curses.color_pair(FG_YELLOW_BG_BLACK))
                    else:
                        mainscreen.addstr(c, 0, text, curses.color_pair(FG_YELLOW_BG_BLACK))
                    c += 1
                else:
                    if len(treeview_levels) > last_fline:
                        visible += 1
                        text = "+ {} more lines".format(len(treeview_levels)-last_fline).ljust(cols)
                        mainscreen.addstr(last_fline, 0, text, curses.color_pair(FG_CYAN_BG_BLACK))
                    break

            if drawn:
                prev = -100
                for d in drawn:
                    ( level, line, name ) = treeview_levels[d]
                    if level > 0:
                        if d != prev + 1:
                            n = prev + 1
                            (prev_level, _, _) = treeview_levels[prev]
                            while n < d:
                                mainscreen.addstr(n, (prev_level) * 2, "│", curses.A_BOLD|curses.color_pair(FG_YELLOW_BG_BLACK))
                                n = n+1
                        mainscreen.addstr(d, (level-1) * 2, "└─", curses.A_BOLD|curses.color_pair(FG_YELLOW_BG_BLACK))
                    prev = d

    darklines = (lines - 2)
    if visible < darklines:
        for z in range(visible, darklines):
            mainscreen.addstr(z, 0, ' ' * cols)

    mainscreen.addstr(lines-2, 0, (" {} {}".format(icon, ''.join(searchstr))).ljust(cols), curses.A_BOLD|curses.color_pair(FG_WHITE_BG_BLUE))
    mainscreen.move(lines-2, len(searchstr) + 3)
    #mainscreen.refresh();



def path_splitter(p):
    """
    Recursively split file-path into name + parent
    """
    t,r = os.path.split(p)
    if t:
        xx = path_splitter(t)
        return xx + [(t, r)]
    elif r:
        return [('', r)]
    return []



def create_levels():
    """
    Build tree from matches, then flatten it sort of..
    """
    global hits
    global treeview_levels

    line = 0          # we flatten the tree to a list of lines
    used = set()      # we only include directories once
    cache = dict()    # what dirs are connected to files?
    curr_levels = []  # we need two passed to calculate levels

    for f in hits:
        path_tokens = path_splitter(f)
        levels = []
        for i,x in enumerate(path_tokens):
            name = x[1]
            if i < len(path_tokens) -1:
                name = "▽ {}".format(name)
            levels.append( (i, line, x[0], name, os.path.join(x[0],x[1])) )
        #easylog("path.levels: {} => {}".format(f, levels))
        line += 1
        for l in levels:
            (level, xline, parent, name, fullpath) = l
            if (fullpath not in used):
                used.add(fullpath)
                curr_levels.append(( level, xline, name, fullpath ))
                cache[fullpath] = [ xline ]
            else:
                cache[fullpath].append(xline)

    #for k in cache: easylog("{} => {}".format(k, cache[k]))

    treeview_levels = []
    for c in curr_levels:
        ( level, xline, name, fullpath ) = c
        treeview_levels.append( (level, cache[fullpath], name) )

    

def find_files():
    """
    Find all files in root directory/diretories
    """
    global roots
    global files
    global hits

    for root in roots:
        if not os.path.isdir(root):
           sys.stderr.write("[ERROR] directory not found: {}\n".format(root))
           raise SystemExit(1)
        for r, dirs, f in os.walk(root):
            dirs[:] = [ d for d in dirs if d not in skipdirs ]
            files += [ os.path.join(r, x) for x in f if x not in skipfiles ]
    hits = files
    create_levels()


def main():
    """
    Entry point
    """
    global roots
    global mainscreen
    global editor
    global fzf_match


    (opts, args) = niceopt(sys.argv[1:], "hvfe:",
                           ['help','version','fzf','editor='])

    for o, a in opts:
        if o in ('-h', '--help'):
            print( __doc__ )
            raise SystemExit(0)
        if o in ('-v', '--version'):
            print( "{} - {}".format(os.path.basename(sys.argv[0]), __version__))
            raise SystemExit(0)
        if o in ('-f', '--fzf'):
            fzf_match = True
        if o in ('-e', '--editor'):
            editor = a

    if len(args) > 0:
        roots = args

    find_files()
    bind_ctrlc_etc()
    mainscreen = init_curses_screen()
    restore_state()
    mainloop()
    quit_peacefully()



if __name__ == '__main__':
    main()
