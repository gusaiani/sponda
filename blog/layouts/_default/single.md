{{- /*
  The markdown twin of a blog post, served at the post's permalink plus
  `index.md`.

  `.RenderShortcodes` rather than `.RawContent`: it expands shortcodes while
  leaving the surrounding markdown exactly as written, so a reader gets the
  author's prose and a real URL where the video embed was, instead of the
  literal shortcode tag.
*/ -}}
# {{ .Title }}
{{ with .Date }}
> {{ .Format "2006-01-02" }}
{{- end }}
{{- with .Params.description }}
>
> {{ . }}
{{- end }}

{{ .RenderShortcodes }}

---

[{{ .Site.Title }}]({{ .Site.Params.mainSiteURL }}){{ with .OutputFormats.Get "html" }} · [{{ .Permalink }}]({{ .Permalink }}){{ end }}
