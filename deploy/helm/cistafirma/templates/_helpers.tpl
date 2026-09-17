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

{{/*
The address the frontend's nginx proxies to.

Computed from the same `fullname` that names the backend Service below rather
than written out a second time, because these two names have to meet and
nothing used to check that they did. They did not: the chart names the Service
`<release>-cistafirma-backend`, the image has `cistafirma-backend` baked in as
its default (that is the *kustomize* Service name), and the docs and CI install
releases called `cistafirma-dev` / `cistafirma-prod`. Rendering with only the
resolver supplied would have produced 502s on every request with the pod
reporting healthy, since the frontend probe is deliberately blind to the
backend. One name is now derived from the other, so it cannot drift again.
*/}}
{{- define "cistafirma.backendUpstream" -}}
{{- printf "%s-backend:8000" (include "cistafirma.fullname" .) -}}
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

