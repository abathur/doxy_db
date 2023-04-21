{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/8ad5e8132c5dcf977e308e7bf5517cc6cc0bf7d8";
    flake-utils.url = "github:numtide/flake-utils";
    flake-compat = {
      url = "github:edolstra/flake-compat";
      flake = false;
    };
  };

  description = "A smol (quick) git status prompt plugin";

  outputs = { self, nixpkgs, flake-utils, flake-compat }:
    {
      overlays.default = final: prev: {
        doxy_db = prev.callPackage ./doxy_db.nix { };
        doxygen_sqlite3 = prev.callPackage ./doxygen_sqlite3.nix { };
      };
      # shell = ./shell.nix;
    } // flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            self.overlays.default
          ];
        };
      in
        {
          packages = {
            inherit (pkgs) doxy_db;
            default = pkgs.doxy_db;
          };
          checks = pkgs.callPackages ./test.nix {
            inherit (pkgs) doxygen_sqlite3;
          };
          # devShells = {
          #   default = pkgs.mkShell {
          #     buildInputs = [ pkgs.doxy_db pkgs.bashInteractive ];
          #     shellHook = ''
          #       exec /usr/bin/env -i LILGITBASH="${pkgs.lilgit}/bin/lilgit.bash" ${pkgs.bashInteractive}/bin/bash --rcfile ${demo} --noprofile -i
          #     '';
          #   };
          #   update = pkgs.callPackage ./update.nix { };
          # };
        }
    );
}
