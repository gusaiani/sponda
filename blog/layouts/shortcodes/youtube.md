{{- /*
  The markdown rendering of a YouTube embed.

  The HTML output format gets Hugo's built-in iframe. A reader of the .md
  twin wants the URL, not markup it cannot render.
*/ -}}
[YouTube: https://www.youtube.com/watch?v={{ .Get 0 }}](https://www.youtube.com/watch?v={{ .Get 0 }})
