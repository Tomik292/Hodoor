# -*- coding: utf-8 -*-
# Generated by Django 1.9.6 on 2017-06-21 12:13
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0026_auto_20170619_1700'),
    ]

    operations = [
        migrations.RenameField(
            model_name='profile',
            old_name='contract',
            new_name='contracts',
        ),
    ]
