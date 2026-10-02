# CodePreview

A scrolling, monospace preview of the generated Markdown inside a group.

**Use** for read-only text output. The page provides the text (cut at 60,000 characters with a footer saying so).

- `code` style in `label`, 16px padding, at most 300px tall, wraps long lines.
- `unicode-bidi: plaintext`: each line takes its own direction, so Arabic lines align right and English ones left in the same preview.
