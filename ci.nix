{ pkgs ? import <nixpkgs> {} }:

let mine = rec {
	doxygen = pkgs.doxygen.overrideAttrs (attrs: {
	  name = "doxygen-1.8.15-sqlite3gen";
	  src = pkgs.fetchFromGitHub {
	    owner  = "abathur";
	    repo   = "doxygen";
	    rev    = "65df7145398668285ab9403593a254d09f10d5b3";
	    sha256 = "1gkbixpwmnvi99bcz24px8na254q6bkz23701mnn8j8jmqxq2nbp";
	  };
	  buildInputs = attrs.buildInputs ++ [ pkgs.sqlite ];
	  cmakeFlags = [
	    "-Duse_sqlite3=ON"
	  ] ++ attrs.cmakeFlags;
	});
	# doxygen = pkgs.doxygen.overrideAttrs (attrs: {
	#   name = "doxygen-1.8.15-sqlite3gen";
	#   src = ./.;
	#   # dontStrip = true;
	#   buildInputs = attrs.buildInputs ++ [ pkgs.sqlite ];
	#   cmakeFlags = [
	#     "-Duse_sqlite3=ON"
	#   ] ++ attrs.cmakeFlags;
	# });
	doxy_db = pkgs.python36Packages.buildPythonPackage rec {
	  pname = "doxy_db";
	  version = "0.0.1";
	  name = "${pname}-${version}";
	  src = ./.;

	  DOXYGEN_EXAMPLES_DIR = "${mine.doxygen.src}/examples";

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
	  export COLUMNS=140 # just overriding to tidy output
	  '';
	  postCheck = ''
	  # clean up? irrelevant on CI, but useful locally
	  rm -rf doxy_db/tests/xml
	  rm doxy_db/tests/doxygen_sqlite3.db
	  '';

	};
};

in pkgs.stdenv.mkDerivation rec {
	name = "env";
	COLUMNS = 160;
	buildInputs = with mine; [
		doxy_db
		# black is still only in nixpkgs-unstable; it should work on travis-ci, but it'll break locally unless we explicitly specify nixpkgs-unstable when we build (-I nixpkgs=https://github.com/NixOS/nixpkgs-channels/archive/nixpkgs-unstable.tar.gz). This takes forever, so we aren't going to do it more than once.
		pkgs.unixtools
		pkgs.python3Packages.black
		pkgs.python36Packages.flake8
		pkgs.python36Packages.pytestcov
	];
}
