# -*- coding: utf-8 -*-
"""
KaTeX Math Processor for Pelican
================================
"""

import codecs
import pickle
import json
import html
import logging
import os
import subprocess


LOG = logging.getLogger(__name__)
INCLUDE_TYPES = ['.html']
SAVE_CACHE = True

tokens = (
    'LATEX_INLINE',
    'LATEX_DISPLAY',
    'HTML',
)


def t_LATEX_INLINE(t):
    r'<tt\s+class="math">([\S\s]+?)</tt>'
    global lexer
    groups = lexer.lexmatch.groups()
    if len(groups) > 1:
        t.value = groups[1]
    return t


def t_LATEX_DISPLAY(t):
    r'<pre\s+class="math">([\S\s]+?)</pre>'
    global lexer
    groups = lexer.lexmatch.groups()
    if len(groups) > 3:
        t.value = groups[3]
    return t


t_HTML = r'[\S\s]'


def t_error(t):
    LOG.error("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


import ply.lex as lex
lexer = lex.lex()


def load_cache():
    try:
        with open('katex_cache.json', 'r') as fp:
            return {(key[1:], key[0] == '1'): value
                    for key, value in json.load(fp).items()}
    except IOError:
        LOG.info('KaTeX: Could not find KaTeX cache file katex_cache.json')
    return {}


def save_cache(katex_cache):
    with open('katex_cache.json', 'w') as fp:
        json.dump({('1' if display else '0') + key: value
                   for (key, display), value
                   in katex_cache.items()},
                  fp, indent=0, sort_keys=True, ensure_ascii=False)


def process_files(pelican):
    """
    Preprocess a generated HTML file to replace LaTex  with math HTML
    """
    katex_cache = {}
    if SAVE_CACHE:
        katex_cache = load_cache()
        LOG.info('KaTeX: Initialized katex cache with {0} entries.'
                 .format(len(katex_cache)))

    for dirpath, _, filenames in os.walk(pelican.settings['OUTPUT_PATH']):
        for name in filenames:
            if should_process(name):
                filepath = os.path.join(dirpath, name)
                process_file(filepath, katex_cache)

    if SAVE_CACHE:
        save_cache(katex_cache)
        LOG.info('KaTeX: Saved katex cache with {0} entries.'
                 .format(len(katex_cache)))


def katex(latex, display_mode, katex_cache):
    if (latex, display_mode) in katex_cache:
        return katex_cache[latex, display_mode]

    args = ['katex']
    if display_mode:
        args.append('-d')
    katex = subprocess.Popen(args=args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    katex.stdin.write(latex.encode('utf-8'))
    katex.stdin.close()
    result = katex.stdout.read().decode('utf-8')
    katex.terminate()

    katex_cache[latex, display_mode] = result
    return result


def write_output(content, katex_cache, output_file):
    lexer.input(content)
    while True:
        tok = lexer.token()
        if not tok:
            return
        if tok.type == 'HTML':
            output_file.write(tok.value)
        else:
            display_mode = tok.type != 'LATEX_INLINE'
            katex_result = katex(html.unescape(tok.value), display_mode, katex_cache)
            output_file.write(katex_result)


def process_file(filename, katex_cache):
    content = ''
    with open(filename, 'r') as f:
        content = f.read()
    if not content:
        return
    LOG.info('KaTeX: Processing {0}'.format(filename))
    with open(filename, 'w') as output_file:
        write_output(content, katex_cache, output_file)


def should_process(filename):
    """
    Check if the filename is a type of file that should be processed.
    :param filename: A file name to check against
    """
    return any(filename.endswith(extension) for extension in INCLUDE_TYPES)


def register():
    """
    Register Pelican signal for modifying content after it is generated.
    """
    from pelican import signals
    signals.finalized.connect(process_files)
