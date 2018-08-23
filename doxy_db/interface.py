"""
A small interface to a doxygen database manual.

This API is intended to sit above the manual's abstraction level to minimize the knowledge a consumer needs to have of Doxygen's idioms.

It may meet your needs out of the box, but it probably won't meet everyone's. Even if it doesn't fit your needs, it should be useful for understanding how to interact with the underlying APIs to tailor something to your needs.
"""

from lxml import html
from functools import lru_cache
import json


#


class XMLTranslator(object):
    """
    A very minimal XML translator. Only attempts to strip tags and provide a tolerable plaintext experience.

    Multiple doxygen documentation fields can contain complex entities that can't be sensibly rendered in plaintext (including HTML, markdown, doxygen commands, and so on). The only sensible non-destructive action the SQLite3 generator can take is to output these as XML.

    It would be nice to accumulate a small selection of fairly generic XML translators here over time, but I think this is best driven by real-world usage.

    To extend this class:
    - add or override methods with the name of an XML node
    - change the node's text or tail inline if needed
    - return beforeText, afterText
    """

    @lru_cache(maxsize=2048)
    def __call__(self, desc):
        if not desc or not len(desc):
            return None
        nodes = map(
            self.__outer_paragraphs__,
            # We have to use HTML; xml parser blew up on many desc fields
            html.fragment_fromstring(desc, create_parent=True).iter(),
        )
        return "\n\n".join([x for x in nodes if len(x)]).strip()

    def __outer_paragraphs__(self, node):
        return "".join(map(self.__translate_node__, node.iter()))

    def __translate_node__(self, node):
        # Iterating over nodes yields them depth-first, so we encounter the nodes in the reverse order of our mental model. Since it makes more sense to write the formatter functions in before/after order, we'll flip them here
        after, before = getattr(self, node.tag)(node)
        return "{}{}{}{}".format(
            before or "",
            node.text if node.text else "",
            after or "",
            node.tail if node.tail else "",
        )

    def _default_method(*args):
        return None, None  # before, after

    def __getattr__(self, name):
        return self._default_method

    def listitem(self, node):
        return "* ", "\n"  # before, after


class Cast(object):
    """
    Define output types.

    A little wasteful when we just need Python types, but the abstraction layer vastly simplifies overriding the return types without having to copy-paste the whole Formatter.
    """

    @staticmethod
    def list(items):
        return list(items)

    @staticmethod
    def dict(**kwargs):
        return dict(**kwargs)


class Formatter(object):
    """
    Format returning objects for the consumer.

    This may be a little tricky to keep straight, but try to think of this as tying together a few distinct jobs

    Translate
        Alter document-oriented XML in description fields. The default strips tags and adds minimal plain-text formatting.

    Cast
        Dictate which Python type/class will represent a dict or list. Enables simple re-casting of these types when needed. The default just uses dict and list.

    Format
        Reformat full recordsets before the Interface returns them to the user. This is the ideal place to reformat to JSON/XML/*. The default does 'nothing' (i.e., it allows the 'Cast' types to pass through unaltered).

    Extract
        Package a given record type for output:
        - Specify the generic data type (list or dict) wrapping the whole record.
        - Map data fields from the record to a field/position in the output.
        - Massage field data (translate XML, tokenize, etc.) as needed.

        These methods are named after the namedtuple 'types' defined in makes.py.

    """

    translate = None
    cast = None

    def __init__(self, translate=XMLTranslator(), cast=Cast):
        self.translate = translate
        self.cast = cast

    def __call__(self, record):
        return self.format(self.extract(record))

    def format(self, record):
        return record

    def extract(self, record):
        # call record-specific extractors by name
        return getattr(self, record.__class__.__name__, lambda x: x)(record)

    def populate(self, items):
        return self.cast.list(map(self.extract, items))

    # Extract methods
    def stub(self, stub):
        return self.cast.dict(
            rowid=stub.rowid,
            kind=stub.kind,
            name=stub.name,
            summary=self.translate(stub.summary),
        )

    def member(self, doc):
        return self.cast.dict(
            name=doc.name,
            detaileddescription=self.translate(doc.detaileddescription),
            briefdescription=self.translate(doc.briefdescription),
            inbodydescription=self.translate(doc.inbodydescription),
            definition=doc.definition,
            type=doc.type,
            kind=doc.kind,
        )

    def compound(self, doc):
        return self.cast.dict(
            name=doc.name,
            title=doc.title,
            detaileddescription=self.translate(doc.detaileddescription),
            briefdescription=self.translate(doc.briefdescription),
            kind=doc.kind,
        )

    # No part of the interface lets the user specify relations atm, so for now there's no reason to send them along. When this changes, these need flesh
    member_rel = member
    compound_rel = compound

    def section(self, section):
        return self.cast.dict(
            summary=section.summary,
            children=self.populate(section.children),
            root=section.root,
            type=section.type,
        )

    def metadata(self, meta):
        return self.cast.dict(
            doxygen_version=meta.doxygen_version,
            schema_version=meta.schema_version,
            generated_at=meta.generated_at,
            generated_on=meta.generated_on,
            project_name=meta.project_name,
            project_number=meta.project_number,
            project_brief=meta.project_brief,
        )

    def manual(self, manual):
        return self.cast.dict(
            root=self.extract(manual.root),
            documents=self.populate(manual.documents),
            sections=self.populate(manual.sections),
            meta=self.extract(manual.meta),
        )

    def search(self, results):
        return self.cast.dict(results=self.populate(results.results))


class JSONFormatter(Formatter):
    def format(self, record):
        return json.dumps(record)


class Interface(object):
    """
    High-level interface to a database manual.

    Automates conversions/translations/etc.

    Structure looks a bit like this:
        interface
            - manual
                - documents
                - sections
                    - manuals
                    - views
                        - documents

    However, the interface should have no knowledge about this at the call level. It just knows how to use a formatter unwrap/convert the manual's return types.
    """

    manual = structure = search_tuple = _description = None

    def __init__(self, manual, formatter):
        self.manual = manual
        self._structure = manual.doc_structure()
        self.fmt = formatter
        # TODO: ideal addition to the search tuple is information about the query (and possibly information about how it was executed), which suggests this information (and the tuple) might be better generated down in the manual?
        self.search_tuple = manual.types.get("search")

        # set up LRU caches; we can't use the decorator because they'll globally cache... :(
        self.fetch = lru_cache(maxsize=512)(self.fetch)
        self.search = lru_cache(maxsize=512)(self.search)
        self.brief = lru_cache(maxsize=512)(self.brief)
        self.doc = lru_cache(maxsize=512)(self.doc)

    def _disambiguate(self, results):
        return self.search_tuple(results)

    # I don't think this actually needs a public API?
    # def disambiguate(self, results):
    #     return self.fmt(self._disambiguate(results))

    def fetch(self, rowid):
        return self.manual.doc_fetch(rowid)

    def search(self, query):
        return self.fmt(self.search_tuple(self.manual.doc_search(query)))

    def _brief(self, query):
        results = self.manual.doc_search(query)
        if len(results) == 1:
            return results[0]
        else:
            return self._disambiguate(results)

    def brief(self, query):
        ob = self._brief(query)
        return self.fmt(ob)

    def _doc(self, query):
        results = self.manual.doc_search(query)
        stub = None
        if len(results) == 1:
            stub = results[0]
        else:
            return self._disambiguate(results)

        return self.fetch(stub.rowid)

    def doc(self, query):
        ob = self._doc(query)
        return self.fmt(ob)

    def structure(self):
        return self.fmt(self._structure)
