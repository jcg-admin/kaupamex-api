"""Compara dos JUnit, con la referencia y sin ella.

Imprime la población dependiente: las pruebas que cambian de resultado.
"""
import collections
import sys
import xml.etree.ElementTree as ET


def outcomes(path):
    result = {}
    for case in ET.parse(path).iter('testcase'):
        key = f"{case.get('classname')}::{case.get('name')}"
        state = 'passed'
        message = ''
        for child in case:
            if child.tag in ('skipped', 'failure', 'error'):
                state = child.tag
                message = (child.get('message') or '')[:120]
        result[key] = (state, message)
    return result


def main(with_path, without_path):
    with_ref, without_ref = outcomes(with_path), outcomes(without_path)
    print('with:', collections.Counter(s for s, _ in with_ref.values()))
    print('without:', collections.Counter(s for s, _ in without_ref.values()))
    only = set(with_ref) ^ set(without_ref)
    print('keys only in one run:', len(only))
    transitions = collections.Counter()
    modules = collections.defaultdict(collections.Counter)
    messages = collections.Counter()
    for key in sorted(set(with_ref) & set(without_ref)):
        before, after = with_ref[key][0], without_ref[key][0]
        if before != after:
            transitions[(before, after)] += 1
            modules[key.split('::')[0].rsplit('.', 1)[0]][(before, after)] += 1
            messages[without_ref[key][1]] += 1
    print('transitions:', dict(transitions))
    for module, counter in sorted(modules.items()):
        print(f'  {module}: {dict(counter)}')
    print('skip messages without reference:')
    for message, count in messages.most_common(10):
        print(f'  {count:5d} {message}')
    failing_with = [k for k, (s, _) in with_ref.items()
                    if s in ('failure', 'error')]
    print('failing with reference:', len(failing_with))
    for key in failing_with[:20]:
        print('  ', key, with_ref[key][1])


if __name__ == '__main__':
    main(*sys.argv[1:3])
