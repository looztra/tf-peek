# Changelog

## [1.3.0](https://github.com/looztra/tf-peek/compare/v1.2.0...v1.3.0) (2026-08-20)


### Features

* **hooks:** install mise-pinned devtools via mise shims ([#114](https://github.com/looztra/tf-peek/issues/114)) ([7794c75](https://github.com/looztra/tf-peek/commit/7794c755f908049588164cb90dd9e200fb56625a))


### Bug Fixes

* **docs:** enable mermaid diagram rendering in mkdocs ([#112](https://github.com/looztra/tf-peek/issues/112)) ([35744b0](https://github.com/looztra/tf-peek/commit/35744b0c5405da1ccf3448906e6191bce6d3113a))

## [1.2.0](https://github.com/looztra/tf-peek/compare/v1.1.0...v1.2.0) (2026-08-19)


### Features

* **cli:** add stdin plan support and load-error diagnostics ([#105](https://github.com/looztra/tf-peek/issues/105)) ([d1e9607](https://github.com/looztra/tf-peek/commit/d1e9607227c6eeb87cb9b1442cd6da51d2c16296))

## [1.1.0](https://github.com/looztra/tf-peek/compare/v1.0.0...v1.1.0) (2026-08-18)


### Features

* **cli:** add --fail-on-critical exit-code gate ([#100](https://github.com/looztra/tf-peek/issues/100)) ([4e05003](https://github.com/looztra/tf-peek/commit/4e050035305b9afb22dbaa660b529dc1faf8ff98))
* **cli:** add --version/-V flag ([236fc4b](https://github.com/looztra/tf-peek/commit/236fc4b390471cb8ea7ec277c28bac936220b2f8))


### Bug Fixes

* **build:** align supported Python versions ([#92](https://github.com/looztra/tf-peek/issues/92)) ([722232c](https://github.com/looztra/tf-peek/commit/722232ceceed3da0032b94c0b5b368cf0049a15b))
* **docs:** remove references to the non-existent `generate` subcommand ([236fc4b](https://github.com/looztra/tf-peek/commit/236fc4b390471cb8ea7ec277c28bac936220b2f8))
* **main:** mask Terraform-sensitive values in report output ([#95](https://github.com/looztra/tf-peek/issues/95)) ([cb1fc97](https://github.com/looztra/tf-peek/commit/cb1fc97da54b0a3171bff776a51979dc10c3a56a))
* **report:** harden rendered Terraform values ([#97](https://github.com/looztra/tf-peek/issues/97)) ([48d85e2](https://github.com/looztra/tf-peek/commit/48d85e256a576c8bbc6cee2bd4d7af292f2c8468))
* **report:** stabilize deterministic changed-property ordering ([#96](https://github.com/looztra/tf-peek/issues/96)) ([5388ba3](https://github.com/looztra/tf-peek/commit/5388ba309ac3f08f5286a6a2d42df3487f0c8eff))

## 1.0.0 (2026-03-07)


### Features

* **cli:** initial implementation with resource tiers, reporting, and docs ([#1](https://github.com/looztra/tf-peek/issues/1)) ([bfc7b09](https://github.com/looztra/tf-peek/commit/bfc7b0981abd98c8b55e740ef6db2242e47d32d5))
