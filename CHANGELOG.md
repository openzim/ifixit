# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2024-03-02

### Changed

- Migrate to Python 3.12
- Upgrade Python dependencies, including zimscraperlib 3.3.1 (#92)
- Adopt Python bootstrap conventions
- ZIM Title is not sourced from online website anymore to match 30 chars limit
- Description and Long Description are set and match openZIM convention
- User pages are not part of search / suggestion results anymore (#85)

### Fixed

- iFixit API is returning "null" when listing category (#93)

## [0.2.4] - 2023-01-05

### Fixed

- Adapt to changes in upstream iFixit main page HTML content

## [0.2.3] - 2022-10-20

### Fixed

- Do not process unrecognized href, i.e. pointing outside iFixit

## [0.2.2] - 2022-10-04

### Fixed

- Fixed URL normalization on articles redirecting outside domain (help.ifixit.com)

## [0.2.1] - 2022-06-02

### Fixed

- Report more clearly in the log when no ZIM is produced on-purpose + produce the ZIM even if some error occured
- Remove unused log about number of images scrapped
- Fix issue with unquoted normalized URLs before regex matching
- Some users have changed their username
- Some users have a quote in their username
- Ignore irelevant info pages
- Some users do not have a username
- URLs of missing items are not encoded properly
- Issues with the "Load more comments" button in guides

## [0.2.0] - 2022-05-04

### Added

- Render tools and parts on guides / categories
- Render comments on guides
- Scrape user pages (only the ones linked as an author or in a comment)
- Use a nice looking URL scheme (instead of the previous technical one)
- Report about scraper progression (usefull for ZimFarm monitoring)
- Add a nice page for missing / error items to avoid dead links
- Add a nice looking page for external URLs
- Handle URL-encoded category titles found in links
- Handle unapproved category translations
- Handle most unscrapped iFixit URLs appropriately (redirect to a nice page)
- Detect duplicate images and replace them with a redirect
- Documentation for PyPi installation

### Fixed
- Fix issue about items being scrapped twice due to int / str difference
- Fix issue about ANCHOR links

## [0.1.0] - 2022-04-17

### Added

- initial version
