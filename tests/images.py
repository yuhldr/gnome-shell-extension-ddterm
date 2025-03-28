#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 Aleksandr Mezin <mezin.alexander@gmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import itertools
import json
import pathlib
import subprocess

import yaml


THIS_FILE = pathlib.Path(__file__).resolve()
THIS_DIR = THIS_FILE.parent
COMPOSE_FILE = THIS_DIR / 'compose.yaml'


def resolve_images(compose_config, services):
    services_config = compose_config['services']

    if services:
        services = [services_config[name] for name in services]
    else:
        services = services_config.values()

    return set(s['image'] for s in services)


def run_prune_resolved(images, dry_run=False):
    image_names = set(i.split(':')[0] for i in images)

    local_images_json = json.loads(
        subprocess.run(
            ('podman', 'image', 'ls', '--format=json', *(f'-f=reference={i}' for i in image_names)),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout
    )

    for i in itertools.chain.from_iterable(i['Names'] for i in local_images_json):
        if i in images:
            continue

        if dry_run:
            print(i)
        else:
            try:
                subprocess.run(('podman', 'image', 'rm', i), check=True)
            except subprocess.CalledProcessError as ex:
                print(ex)


def run_prune(compose_config, services, **kwargs):
    run_prune_resolved(
        images=resolve_images(compose_config, services),
        **kwargs
    )


def run_pull(compose_config, services, prune=False):
    images = resolve_images(compose_config, services)

    subprocess.run(('podman', 'image', 'pull', *images), check=True)

    if prune:
        run_prune_resolved(images)


def run_command(func, file, **kwargs):
    with open(file) as f:
        compose_config = yaml.safe_load(f)

    func(compose_config=compose_config, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        description='Manage container images'
    )

    parser.add_argument(
        '-f', '--file',
        type=pathlib.Path,
        default=COMPOSE_FILE,
        help='configuration file path'
    )

    subparsers = parser.add_subparsers(required=True)

    pull_parser = subparsers.add_parser(
        'pull',
        help='Download/update images'
    )

    pull_parser.add_argument(
        'services',
        nargs='*',
        help='Names of the services (as specified in compose.yaml) to download images for'
    )

    pull_parser.add_argument(
        '--prune',
        action='store_true',
        help='Remove outdated images (i.e. images with the same name but mismatching tag)'
    )

    pull_parser.set_defaults(func=run_pull)

    prune_parser = subparsers.add_parser(
        'prune',
        help='Remove outdated images (i.e. images with the same name but mismatching tag)'
    )

    prune_parser.add_argument(
        'services',
        nargs='*',
        help='Names of the services (as specified in compose.yaml) to prune images for'
    )

    prune_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Do not delete images, just print their names'
    )

    prune_parser.set_defaults(func=run_prune)

    run_command(**vars(parser.parse_args()))


if __name__ == '__main__':
    main()
