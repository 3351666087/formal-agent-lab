{{- define "fal.name" -}}{{ .Chart.Name }}{{- end -}}
{{- define "fal.fullname" -}}{{ printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "fal.labels" -}}
app.kubernetes.io/name: {{ include "fal.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
{{- define "fal.selector" -}}
app.kubernetes.io/name: {{ include "fal.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}
{{- define "fal.image" -}}
{{- $img := index .root.Values.image .component -}}
{{- $repo := ternary (printf "%s/%s" .root.Values.image.registry $img.repository) $img.repository (ne .root.Values.image.registry "") -}}
{{- if $img.digest -}}{{ printf "%s@%s" $repo $img.digest }}{{- else -}}{{ printf "%s:%s" $repo .root.Values.image.tag }}{{- end -}}
{{- end -}}
{{- define "fal.env" -}}
- name: FAL_DATABASE_URL
  valueFrom: { secretKeyRef: { name: {{ .Values.externalServices.database.existingSecret }}, key: {{ .Values.externalServices.database.urlKey }} } }
- name: FAL_TEMPORAL_ADDRESS
  value: {{ .Values.externalServices.temporal.address | quote }}
- name: FAL_TEMPORAL_NAMESPACE
  value: {{ .Values.externalServices.temporal.namespace | quote }}
- name: FAL_TEMPORAL_TASK_QUEUE
  value: {{ .Values.externalServices.temporal.taskQueue | quote }}
- name: FAL_DEPLOYMENT_PROFILE
  value: {{ .Values.deploymentProfile | quote }}
- name: FAL_ARTIFACT_BACKEND
  value: {{ .Values.externalServices.artifacts.backend | quote }}
{{- if eq .Values.externalServices.artifacts.backend "s3" }}
{{- $s3 := .Values.externalServices.artifacts.s3 }}
- name: FAL_S3_ENDPOINT_URL
  value: {{ $s3.endpoint | quote }}
- name: FAL_S3_BUCKET
  value: {{ $s3.bucket | quote }}
- name: FAL_S3_REGION
  value: {{ $s3.region | quote }}
- name: FAL_S3_ACCESS_KEY_ID
  valueFrom: { secretKeyRef: { name: {{ $s3.existingSecret }}, key: {{ $s3.accessKeyKey }} } }
- name: FAL_S3_SECRET_ACCESS_KEY
  valueFrom: { secretKeyRef: { name: {{ $s3.existingSecret }}, key: {{ $s3.secretKeyKey }} } }
{{- else }}
- name: FAL_ARTIFACT_ROOT
  value: /var/lib/fal/artifacts
{{- end }}
{{- if .Values.llm.enabled }}
- name: FAL_LLM_BASE_URL
  valueFrom: { secretKeyRef: { name: {{ .Values.llm.existingSecret }}, key: base-url } }
- name: FAL_LLM_API_KEY
  valueFrom: { secretKeyRef: { name: {{ .Values.llm.existingSecret }}, key: api-key } }
- name: FAL_LLM_MODEL
  valueFrom: { secretKeyRef: { name: {{ .Values.llm.existingSecret }}, key: model } }
{{- end }}
{{- end -}}
