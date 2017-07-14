# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-07-12 11:34
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0048_auto_20170712_1119'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='profile',
            name='last_action_time',
        ),
        migrations.AlterField(
            model_name='profile',
            name='aviable_holidays',
            field=models.FloatField(default=0, verbose_name='Already aviable holideys in hours'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='weeks_of_holidays_per_year',
            field=models.IntegerField(default=4),
        ),
    ]