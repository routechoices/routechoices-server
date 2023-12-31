<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>
  <xsl:strip-space elements="*"/>
  <xsl:template match="/">
    <html xmlns="http://www.w3.org/1999/xhtml" lang="en">
      <head>
        <title>
          RSS Feed |
          <xsl:value-of select="/rss/channel/title"/>
        </title>
        <meta charset="utf-8"/>
        <meta http-equiv="content-type" content="text/html; charset=utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <link rel="stylesheet" href="/static/vendor/bootstrap-5.3.2/bootstrap.min.css?v=2023123100"/>
      </head>
      <body>
        <main class="container">
          <div class="py-3">
            <h1 class="flex items-start">
              <!-- https://commons.wikimedia.org/wiki/File:Feed-icon.svg -->
              <svg xmlns="http://www.w3.org/2000/svg" version="1.1"
                   class="mr-5"
                   style="flex-shrink: 0; width: 1em; height: 1em;"
                   viewBox="0 0 256 256">
                <rect width="236" height="236" rx="47" ry="47" x="10" y="10"
                      fill="#FB9E3A"/>
                <circle cx="68" cy="189" r="24" fill="#FFF"/>
                <path
                  d="M160 213h-34a82 82 0 0 0 -82 -82v-34a116 116 0 0 1 116 116z"
                  fill="#FFF"/>
                <path
                  d="M184 213A140 140 0 0 0 44 73 V 38a175 175 0 0 1 175 175z"
                  fill="#FFF"/>
              </svg>
              RSS Feed
            </h1>
            <edent-alert-box type="info">
              <strong>This is an RSS feed</strong>. You can subscribe by copying the URl from the address bar into your newsreader. Visit <a href="https://aboutfeeds.com">About Feeds</a> to learn more and get started.
            </edent-alert-box>
            <h2 class="pt-3"><xsl:value-of select="/rss/channel/title"/></h2>
            <p>
              Updated on <xsl:value-of select="/rss/channel/lastBuildDate"/>
            </p>
            <a>
              <xsl:attribute name="href">
                <xsl:value-of select="/rss/channel/link"/>
              </xsl:attribute>
              Go to the club's page
            </a>

            <h2 class="pt-3">Recent events</h2>
            <xsl:for-each select="/rss/channel/item">
              <div class="pb-3">
                <div class="text-4 font-bold">
                  <a>
                    <xsl:attribute name="href">
                      <xsl:value-of select="link"/>
                    </xsl:attribute>
                    <xsl:value-of select="title" disable-output-escaping="yes"/>
                  </a>
                </div>

                <div class="small">
                  Published on
                  <xsl:value-of select="substring(pubDate, 0, 17)" />
                </div>
              </div>
            </xsl:for-each>
          </div>
        </main>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
