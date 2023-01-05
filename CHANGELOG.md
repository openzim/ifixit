# 0.2.4

- Adapt to changes in upstream iFixit main page HTML content

# 0.2.3

- Do not process unrecognized href, i.e. pointing outside iFixit

# 0.2.2

- Fixed URL normalization on articles redirecting outside domain (help.ifixit.com)

# 0.2.1
See [milestone](https://github.com/openzim/ifixit/milestone/3) for advanced details.

Small bugs fixes:
- Report more clearly in the log when no ZIM is produced on-purpose + produce the ZIM even if some error occured
- Remove unused log about number of images scrapped 
- Fix issue with unquoted normalized URLs before regex matching 
- Some users have changed their username 
- Some users have a quote in their username 
- Ignore irelevant info pages
- Some users do not have a username 
- URLs of missing items are not encoded properly
- Issues with the "Load more comments" button in guides 

# 0.2.0
See [milestone](https://github.com/openzim/ifixit/milestone/1) for advanced details.

- Render tools and parts on guides / categories
- Render comments on guides
- Scrape user pages (only the ones linked as an author or in a comment)
- Use a nice looking URL scheme (instead of the previous technical one)
- Report about scraper progression (usefull for ZimFarm monitoring)
- Fix issue about items being scrapped twice due to int / str difference
- Fix issue about ANCHOR links
- Add a nice page for missing / error items to avoid dead links
- Add a nice looking page for external URLs
- Handle URL-encoded category titles found in links
- Handle unapproved category translations
- Handle most unscrapped iFixit URLs appropriately (redirect to a nice page)
- Detect duplicate images and replace them with a redirect
- Documentation for PyPi installation


# 0.1.0

- initial version
