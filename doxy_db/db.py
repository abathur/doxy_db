import sqlite3

from . import sql
from . import views
from . import exceptions
from . import makes


class DoxygenSQLite3(object):
    """TODO"""

    indexpage = None
    connection = None
    types = None

    def __init__(
        self,
        uri,
        type_factory=makes.default_types,
        atom_factory=makes.default_atoms,
        relation_factory=makes.default_relations,
    ):
        self.types = type_factory and type_factory()
        self.atoms = atom_factory and atom_factory()
        self.relations = relation_factory and relation_factory()

        # use URI so that a missing file will error, not implicitly create
        connection = sqlite3.connect("file:{}?mode=rw".format(uri), uri=True)
        connection.row_factory = self.types.row_factory()
        connection.execute("PRAGMA temp_store = MEMORY;")
        self.connection = connection

        # _def is a stepping stone to bigger queries
        self._def = sql.Statement(self).table("def", "rowid")._from("def base")

        self.relview = views.RelationView(
            sql.Statement(self, self._def)._select("*")._where("base.rowid=?")
        )

    # extend and compile are the same logic, but are separate for API semantics/readability.
    def extend(self, func):
        """
        Extend this object's API via a user-specified function.

        def add_api_methods(api):
            api.class_doc = api.make_compound_tree(
                ["class"],
                api.relations.get("methods")
            )
        manual.extend(add_api_methods)
        """
        return func(self)

    def compile(self, func):
        """
        Extend this object's API via a user-specified function.

        def add_sections(man):
            man.mount(
                "example",
                man.class_doc(name="Example_Test")
            )
        manual.compile(add_sections)
        """
        return func(self)

    # ---------------------------------- #

    # View factories; used to extend the API and generate manual sections.
    def topmost(self, kinds, brief_description, search_relation=None):
        """
        Generate a view that will find compounds of 'kinds' that have no parent.

        Note: I thought I could build something similar to the default HTML manual by throwing the page, class, and group kinds through topmost; I was profoundly wrong. There a number of small caveats regarding what appears in those lists and which relations dictate the hierarchy it encodes.
        """
        return views.ListView(
            sql.Statement(self, self._def)._where(
                "base.kind in ('{kinds}') and base.rowid not in (select distinct rowid from inner_outer where [kind:1] in ('{kinds}'))".format(
                    kinds="','".join(kinds)
                )
            ),
            brief_description,
            search_relation=search_relation,
        )

    def kinds(self, kinds, brief_description, search_relation=None):
        """Generate a view that will find  elements of 'kinds' """
        return views.ListView(
            sql.Statement(self, self._def)._where(
                "base.kind in ('{kinds}')".format(kinds="','".join(kinds))
            ),
            brief_description,
            search_relation=search_relation,
        )

    def make_compound_tree(self, kinds, search_relation):
        """
        Generate a factory that itself generates views locked on a certain compound.

        Easier to grasp with an example of how it can be used at a higher layer.

            man.class_doc = man.make_compound_tree(
                ["class"],
                man.relations.get("methods")
            )
            man.mount(
                "example",
                man.class_doc(name="Example_Test")
            )

        First, this creates a view-factory named 'class_doc'. It generates views that will search class compounddefs for one matching a consumer-specified property, lock onto the matched class doc, and support enumerating that class's methods.

        Second, it uses the new view factory to generate a view that targets the Example_Test class, and mounts it as a manual section named 'example'.
        """

        def compound_tree(**kwarg):
            if "refid" in kwarg:
                # TODO: I need to button up the SQL injection attacks present against this module; I'm not sure what import that has for structures like this. They're fine if the caller is in charge of them, but they could prove to be a big footgun if you route a user-provided 'kind' in here...
                return views.DocView(
                    sql.Statement(self, self._def)
                    ._select("base.*")
                    ._where(
                        "base.kind in ('{}') and base.refid='{}'".format(
                            "','".join(kinds), kwarg["refid"]
                        )
                    ),
                    search_relation=search_relation,
                )
            elif "name" in kwarg:
                return views.DocView(
                    sql.Statement(self, self._def)
                    ._select("base.*")
                    ._where(
                        "base.kind in ('{}') and base.name='{}'".format(
                            "','".join(kinds), kwarg["name"]
                        )
                    ),
                    search_relation=search_relation,
                )
            else:
                raise exceptions.InvalidUsage(
                    "compound_tree missing required 'refid' or 'name' argument"
                )

        return compound_tree

    # TODO: I'm skipping a potentially useful method for scaffolding a doc section based on searching a directory for compounds. I took 4 quick swings at this functionality that all ran into intractable problems. I don't want to force a solution, and I don't want to get bogged down in another big segment of functionality before launching.
    #
    # That said, I do want to preserve progress ths far in case it is useful.
    #
    # Here's a basic query that lets you search a directory by name and enumerate its compounds:
    #   select def.* from contains join def on contains.inner_rowid=def.rowid where contains.outer_rowid in (select file.rowid from contains join compounddef on contains.outer_rowid=compounddef.rowid join def file on file.rowid=contains.inner_rowid where compounddef.name='obj');
    #
    # This list-view-based model kinda works for the first couple steps of a deeper search:
    # >>> x.doc_search("std")
    # >>> x.doc_search("std obj_armour")
    #
    # But the last part falls flat on its face:
    #
    # >>> x.doc_search("std obj_armour query_ego")
    # doxy_db.exceptions.MalformedQuery: ('Malformed query', "SELECT [innercompounds].* FROM def base JOIN contains as relative ON base.rowid=relative.outer_rowid JOIN def [innercompounds] ON [innercompounds].rowid=relative.inner_rowid WHERE contains.outer_rowid in (select file.rowid from contains join compounddef on contains.outer_rowid=compounddef.rowid join def as file on file.rowid=contains.inner_rowid where compounddef.name='obj') AND base.rowid=? AND innercompounds.name=?", (381, 'query_ego'))
    #
    # This generated query is broken in like 3 places:
    #
    # - the outer contains.outer_rowid would need to be 'relative.outer_rowid'
    # - the first join contains as relative needs to be on relative.inner_rowid
    # - and, most critically, the query needs additional layers to even begin to actually query members of the intended compound.
    #
    # At a conceptual level, I think this approach runs into a few problems (there might be a less-disruptive approach...):
    # - We need to extend the search_relation concept to an additional layer of depth in order to support first jumping from the directory compound to the appropriate sub-compound and then again to its members
    #   - we could in theory just make the feature a little more rigid, and don't allow a restrictable list? or, use inner_compound, but add a custom 'where kind=?' to the query and let people specify a text kind--but we'll also need to overload the parts of the search/find process that lean on relations for depth search.
    # - I'm not entirely sure if the minimal query wrapper API I built is actually capable of handling queries nesting through this many joins or nested selects very robustly
    #   - and it's probably a fool's-errand to try to develop it to that level of edge-case support
    #   - one potential out might be a more basic raw-query mode. The point of the wrapper is to make easier to build up queries that reference each other's parts, but if this task really is an edge case, that scaffolding isn't essential.
    # - It probably needs its own view or view abstraction; there's just too much edge-case stuff.
    #
    # def directory(self, name, search_relation=None):
    #     # TODO Not quite sure where, but somewhere I need to test and/or doc this behavior.
    #     if search_relation is None:
    #         search_relation = self.relations.get("innercompounds")

    #     return views.ListView(
    #         sql.Statement(self, self._def)
    #         ._select("def.*")
    #         ._from("contains")
    #         ._where("contains.outer_rowid in (select file.rowid from contains join compounddef on contains.outer_rowid=compounddef.rowid join def as file on file.rowid=contains.inner_rowid where compounddef.name='{}')".format(name))
    #         ._join(conditions="def on contains.inner_rowid=def.rowid"),
    #         "Contents of directory {}".format(name),
    #         search_relation=search_relation
    #     )
    #
    # Some other notes I had on this concept elsewhere:
    # - we could cheat and substring fns:
    #   select * from compounddef where kind='class' and id_file in (select rowid from files where name like 'obj/doxy_guide%');
    #   man.mount("std", struct().where(id_file=file().where(name like path%)))
    # - I could imagine a chainable API like: classes(actions).members(**optionally kind="function")

    def root_page(self, field, name):
        return views.DocView(
            sql.Statement(self, self._def)
            ._select(
                ", ".join(
                    ["compounddef.{}".format(x) for x in self.types.cols("compound")]
                )
            )
            ._where("base.kind='page' and base.{}='{}'".format(field, name))
            ._join(conditions="compounddef on compounddef.rowid=base.rowid")
        )
