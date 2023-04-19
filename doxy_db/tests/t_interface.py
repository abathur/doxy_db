# TODO: Not sure how I feel about the json tests in here. They're here because the current formatter is converting to JSON, but I'd like to have more than one formatter. It seems like most of the tests should use a default/None/no-op formatter, and then only a handful of formatter-specific tests should exercise individual formatters... yeah?

import unittest
import json

from .. import manual
from .. import interface
from .. import makes
from . import TEST_DB


def make_manual1():
    man = manual.create(TEST_DB, "test manual 1").compile(manual.doxygen_manual)
    man.mount("pages", man.kinds(["page"], "list of pages"))
    man.mount("functions", man.kinds(["function"], "list of functions"))
    man.publish()
    return man


def non_default_types():
    """Alter a typedef to later confirm returned columns obey typedef."""
    types = makes.default_types()
    types.define(
        "member",
        (
            "rowid",
            "name",
            "kind",
            "definition",
            "type",
            # intentionally omit argsstring
            "scope",
            "inline",
            "bodystart",
            "bodyend",
            "bodyfile_id",
            "line",
            "detaileddescription",
            "briefdescription",
            "inbodydescription",
        ),
    )
    return types


def make_manual2():
    man = manual.create(
        TEST_DB, "test manual 2", type_factory=non_default_types
    ).compile(manual.doxygen_manual)
    man.mount("functions", man.kinds(["function"], "list of functions"))
    man.publish()
    return man


class NoOpXMLTranslator(interface.XMLTranslator):
    @staticmethod
    def __call__(desc):
        return desc


man1 = make_manual1()
man2 = make_manual2()


fmt1 = interface.JSONFormatter(interface.XMLTranslator())
fmt2 = interface.JSONFormatter(NoOpXMLTranslator())
fmt3 = interface.Formatter(interface.XMLTranslator())

api1 = interface.Interface(man1, fmt1)
api2 = interface.Interface(man2, fmt2)
api3 = interface.Interface(man1, fmt3)


class TestInterface(unittest.TestCase):
    brief = json.loads(api1.brief("bug"))
    record = json.loads(api1.doc("bug"))

    def test_brief_vs_doc(self):
        # stub has a 'summary' that generalizes title for a page, but briefdescription for other compounds.
        self.assertEqual(self.brief["name"], self.record["name"])

    def test_disambiguate(self):
        brief_search = json.loads(api1.brief("member"))
        doc_search = json.loads(api1.doc("member"))
        self.assertEqual(len(brief_search["results"]), len(doc_search["results"]))

    def test_empty_search(self):
        brief_search = json.loads(api1.brief("absent_minded_member"))
        doc_search = json.loads(api1.doc("absent_minded_member"))

        # we couldn't normally assert equality of these two different types, but since they'll be empty...
        self.assertEqual(brief_search, doc_search)

    def test_complex_record(self):
        # a little lazy, but we'll say it doesn't have XML if we don't see a '</'
        self.assertNotIn("</", self.record["detaileddescription"])
        # and it'll have a linebreak and an asterisk if there's a listitem in it somewhere
        self.assertIn("\n* ", self.record["detaileddescription"])

    def test_structure(self):
        blob = api1.structure()
        struct = api3.structure()

        self.assertEqual(
            # implicitly tests valid json
            json.loads(blob),
            struct,
        )


class TestMultipleInterfaces(unittest.TestCase):
    """
    Test that a single script/module can instantiate and use two or more manual interfaces.

    Implicitly, this test is about whether state is living in class instances or getting muddled/mixed at the module level.

    Keeping it pretty simple for now. Take two different interfaces and confirm that they can:
    - return distinct column sets,
    - translate XML differently
    - and format records differently
    """

    def test_record_columns(self):
        record1 = api1._doc("main")
        record2 = api2._doc("main")
        # a few tests; take the records and confirm that argsstring is in one but not the other

        self.assertIn("argsstring", record1._fields)
        self.assertNotIn("argsstring", record2._fields)

        # get the dicts from both
        dict1 = record1._asdict()
        dict2 = record2._asdict()

        # but knock out fields we expect to differ
        del dict1["argsstring"]
        del dict1["detaileddescription"]
        del dict2["detaileddescription"]

        self.assertEqual(dict1, dict2)

    def test_xml_translators(self):
        record1 = json.loads(api1.doc("main"))
        record2 = json.loads(api2.doc("main"))
        self.assertNotIn("<para>", record1["detaileddescription"])
        self.assertIn("<para>", record2["detaileddescription"])

    def test_record_formatters(self):
        """
        Output from basic Python datatype formatter and re-loaded output from JSON formatter should be equal
        """
        fmt1 = interface.Formatter(NoOpXMLTranslator())
        fmt2 = interface.JSONFormatter(NoOpXMLTranslator())

        api1 = interface.Interface(man1, fmt1)
        api2 = interface.Interface(man2, fmt2)

        self.assertEqual(api1.search("main"), json.loads(api2.search("main")))
