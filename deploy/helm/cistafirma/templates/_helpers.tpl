{{- define "cistafirma.name" -}}
cistafirma
{{- end -}}

{{- define "cistafirma.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "cistafirma.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "cistafirma.labels" -}}
app.kubernetes.io/name: {{ include "cistafirma.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}

{{- define "cistafirma.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cistafirma.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "cistafirma.backendImage" -}}
{{- printf "%s:%s" .Values.global.backendImage.repository (.Values.global.backendImage.tag | default "latest") -}}
{{- end -}}

{{- define "cistafirma.frontendImage" -}}
{{- printf "%s:%s" .Values.global.frontendImage.repository (.Values.global.frontendImage.tag | default "latest") -}}
{{- end -}}

{{- define "cistafirma.existingSecret" -}}
{{- .Values.global.existingSecret | default (printf "%s-secrets" (include "cistafirma.name" .)) -}}
{{- end -}}

