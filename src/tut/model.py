import functools
import os

from sh import git
import yaml


DEFAULT_CONFIG = {
    'points': [],
}


def with_path(m):

    @functools.wraps(m)
    def _with_path(self, *args, **kwargs):
        start_path = os.getcwd()
        os.chdir(self.path)
        try:
            return m(self, *args, **kwargs)
        finally:
            os.chdir(start_path)

    return _with_path


class TutException(Exception):
    pass


class Tut(object):

    def __init__(self, path):
        self.path = path

    def _repo_dirty(self):
        """Return True if the repository is dirty."""

        UNCHANGED_STATUSES = (' ', '?', '!')

        for status_line in git.status(porcelain=True):
            if not(status_line[0] in UNCHANGED_STATUSES and
                   status_line[1] in UNCHANGED_STATUSES):
                return True

        return False

    def _config(self):
        data = git('--no-pager', 'show', 'tut:tut.cfg')
        return yaml.load(data.stdout)

    def _update_config(self, config, log=None):

        branch = self._current_branch()

        try:
            git.checkout('tut')
            yaml.dump(
                config,
                open('tut.cfg', 'w'),
                default_flow_style=False,
            )
            git.add('tut.cfg')
            git.commit(
                m=log or 'Update configuration.',
            )

        finally:
            git.checkout(branch)

    def init(self):
        """Create a new repository with an initial commit."""

        cwd = os.getcwd()

        # initialize the empty repository
        git.init(self.path)
        os.chdir(self.path)

        git.commit(
            m='Initializing empty Tut project.',
            allow_empty=True,
        )

        # create the empty configuration file
        git.branch('tut')
        self._update_config(
            DEFAULT_CONFIG,
            log='Initializing Tut configuration.',
        )
        git.checkout('master')

        os.chdir(cwd)

    @with_path
    def points(self, remote=None):
        """Return a list of existing checkpoints (branches).

        The list is returned with the oldest checkpoint first.

        """

        return self._config()['points']

    def _current_branch(self):
        """Return the current branch of the repo."""

        return git('rev-parse', '--abbrev-ref', 'HEAD').strip()

    @with_path
    def current(self):
        """Return the name of the current step."""

        current_branch = self._current_branch()

        if current_branch in self.points():
            return current_branch

        return None

    @with_path
    def start(self, name, starting_point=None):
        """Start a new step (branch)."""

        # make sure this is not a known checkpoint
        if name in self.points():
            raise TutException("Duplicate checkpoint.")

        # make sure the repo is clean
        if self._repo_dirty():
            raise TutException("Dirty tree.")

        # create the new branch
        git.branch(name)

        if starting_point is None:
            args = ('-b', name)
        else:
            args = ('-b', name, starting_point, '--track')

        # add the branch to config
        config = self._config()
        points = config['points']
        if self.current():
            points.insert(points.index(self.current()) + 1, name)
        else:
            points.append(name)

        self._update_config(
            config,
            log='Adding new point %s' % name,
        )

        # checkout the new branch
        git.checkout(name)

    @with_path
    def edit(self, name):
        """Start editing the checkpoint point_name."""

        # make sure this is a known checkpoint
        if name not in self.points():
            raise TutException("Unknown checkpoint.")

        # make sure the repo is clean
        if self._repo_dirty():
            raise TutException("Dirty tree.")

        git.checkout(name)

    @with_path
    def next(self, merge=False):
        current = self.current()

        try:
            switch_to = self.points()[
                self.points().index(current) + 1
            ]
        except IndexError:
            # we've reached the end of the list; switch to master
            switch_to = 'master'

        git.checkout(switch_to)

        if merge:
            git.merge(current)
