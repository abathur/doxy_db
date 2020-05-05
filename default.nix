{ pkgs ? import <nixpkgs> {} }:

pkgs.python36Packages.buildPythonPackage rec {
  # building my version of doxygen first
  doxygen = pkgs.doxygen.overrideAttrs (attrs: rec {
    name = "doxygen-1.8.19-sqlite3gen";
    src = pkgs.fetchFromGitHub {
      owner  = "abathur"; # TODO: set back to doxygen when fix is merged
      repo   = "doxygen";
      rev    = "2a6f9d50d606c59e86fe99e4304f056fd7f1032c";
      sha256 = "058f93l23paiwm4h414hnh3yw1hqapp1bni15qivsaysz41g8r9k"; # fix
    };
    buildInputs = attrs.buildInputs ++ [ pkgs.sqlite ];
    cmakeFlags = [
      "-Duse_sqlite3=ON"
    ] ++ attrs.cmakeFlags;
    postInstall = ''
      # put examples in output so doxy_db can test against them
      cp -r ../examples $out/examples
    '';
  });

  # now it's our turn
  pname = "doxy_db";
  version = "0.0.1";
  src = ./.;

  DOXYGEN_ROOT = "${doxygen}";
  DOXYGEN_EXAMPLES_DIR = "${doxygen}/examples";

  checkInputs = [
    pkgs.libxslt
    pkgs.python36Packages.lxml

    doxygen
    pkgs.python36Packages.pytestcov
  ];
  COLUMNS = 114; # override to tidy output
  preCheck = ''
    # build docs
    doxygen examples.conf

    # combine everything into the index
    pushd doxy_db/tests/xml
    xsltproc combine.xslt index.xml > all.xml
    popd
  '';

  # clean up? irrelevant on CI, but useful locally
  postCheck = ''
    rm -rf doxy_db/tests/xml doxy_db/tests/doxygen_sqlite3.db
  '';
}
