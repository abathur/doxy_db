{ pkgs ? import <nixpkgs> {} }:

pkgs.python36Packages.buildPythonPackage rec {
	# building my version of doxygen first
	doxygen = pkgs.doxygen.overrideAttrs (attrs: {
	  name = "doxygen-1.8.15-sqlite3gen";
	  src = pkgs.fetchFromGitHub {
	    owner  = "abathur";
	    repo   = "doxygen";
	    rev    = "61cddaf2d440aff48868fc3a50185a2788917914";
	    sha256 = "10p0968daz3l0r1la4nzivxvmbb2c9515piidq64c02ky3gmwnf9";
	  };
	  buildInputs = attrs.buildInputs ++ [ pkgs.sqlite ];
	  cmakeFlags = [
	    "-Duse_sqlite3=ON"
	  ] ++ attrs.cmakeFlags;
	});

	# now it's our turn
	pname = "doxy_db";
	version = "0.0.1";
	name = "${pname}-${version}";
	src = ./.;

	DOXYGEN_ROOT = "${doxygen.src}";
	DOXYGEN_EXAMPLES_DIR = "${doxygen.src}/examples";

	checkInputs = [
		pkgs.libxslt
		pkgs.python36Packages.lxml

		doxygen
		pkgs.python36Packages.pytestcov
	];
	preCheck = ''
	doxygen examples.conf # build docs
	# combine everything into the index
	cd doxy_db/tests/xml
	xsltproc combine.xslt index.xml > all.xml
	cd ../../../
	export COLUMNS=114 # just overriding to tidy output
	'';
	postCheck = ''
	# clean up? irrelevant on CI, but useful locally
	rm -rf doxy_db/tests/xml
	rm doxy_db/tests/doxygen_sqlite3.db
	ls -la doxy_db/tests
	'';
}
