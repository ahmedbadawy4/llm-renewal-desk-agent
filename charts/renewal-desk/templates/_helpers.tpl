{{- define "renewal-desk.name" -}}
renewal-desk
{{- end }}

{{- define "renewal-desk.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride -}}
{{- else -}}
{{- .Release.Name -}}
{{- end -}}
{{- end -}}

{{- define "renewal-desk.labels" -}}
app.kubernetes.io/name: {{ include "renewal-desk.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
