from django.db import models


class ETLExecutionLog(models.Model):
    etl_name = models.CharField(max_length=100)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('RUNNING', 'Running'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ])
    records_processed = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    triggered_by = models.CharField(max_length=50, choices=[
        ('SCHEDULER', 'Scheduled Task'),
        ('MANUAL', 'Manual Execution'),
    ])

    class Meta:
        ordering = ['-started_at']
