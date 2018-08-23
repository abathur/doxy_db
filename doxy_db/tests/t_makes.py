# TODO: This is pretty anemic. The vast majority of makes.py gets exercised implicitly, so explicit testing isn't terribly high-value...

import unittest

from .. import makes
from .. import exceptions

atoms = makes.default_atoms()


class TestAtoms(unittest.TestCase):
    def test_names(self):
        atoms.names()

    def test_undefined_atom(self):
        with self.assertRaises(exceptions.RequiredRelationAtomMissing):
            atoms.get("pasta")
