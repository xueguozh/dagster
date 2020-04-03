dagster_aws
===========

.. currentmodule:: dagster_aws

S3
--

.. autoclass:: dagster_aws.s3.S3ComputeLogManager

.. autoclass:: dagster_aws.s3.S3FileCache
  :members:

.. autoclass:: dagster_aws.s3.S3FileHandle
  :members:

.. autodata:: dagster_aws.s3.s3_resource
  :annotation: ResourceDefinition

.. autodata:: dagster_aws.s3.S3Coordinate
  :annotation: DagsterType

  A :py:class:`dagster.DagsterType` intended to make it easier to pass information about files on S3
  from solid to solid. Objects of this type should be dicts with ``'bucket'`` and ``'key'`` keys,
  and may be hydrated from config in the intuitive way, e.g., for an input with the name
  ``s3_file``:

  .. code-block:: YAML

      inputs:
        s3_file:
          value:
            bucket: my-bucket
            key: my-key


.. autodata:: dagster_aws.s3.s3_system_storage
  :annotation: SystemStorageDefinition

.. autodata:: dagster_aws.s3.s3_plus_default_storage_defs
  :annotation: List[SystemStorageDefinition]

  The default system storages available on any :py:class:`~dagster.ModeDefinition` that does not
  provide custom system storages, i.e., :py:class:`~dagster.default_system_storage_defs` plus the
  :py:class:`s3_system_storage`.


Testing
^^^^^^^

.. autoclass:: dagster_aws.s3.S3FakeSession
  :members:

.. autofunction:: dagster_aws.s3.create_s3_fake_resource


Redshift
--------
.. autodata:: dagster_aws.redshift.redshift_resource
  :annotation: ResourceDefinition


Testing
^^^^^^^

.. autodata:: dagster_aws.redshift.fake_redshift_resource
  :annotation: ResourceDefinition


EMR
---

.. autodata:: dagster_aws.emr.emr_pyspark_resource
  :annotation: ResourceDefinition

.. autoclass:: dagster_aws.emr.EmrJobRunner

.. autoclass:: dagster_aws.emr.EmrError

.. autodata:: dagster_aws.emr.EmrClusterState

.. autodata:: dagster_aws.emr.EmrStepState


CloudWatch
----------

.. autodata:: dagster_aws.cloudwatch.cloudwatch_logger
  :annotation: LoggerDefinition


-----


CLI
---

The ``dagster_aws`` package includes a CLI tool intended to help you get a demo Dagster
up and running as quickly as possible. Please see the `docs <../../../deploying/aws.html>`_ for details.

**NOTE: The dagster-aws CLI is not intended to provide a secure configuration, and the instance
it sets up will be launched into an existing VPC and publicly accessible. In production settings,
you will want to launch Dagit into an appropriately configured VPC, using an appropriate security
group, etc. Please see the docs for details.**

.. click:: dagster_aws.cli.cli:delete
   :prog: dagster-aws delete

.. click:: dagster_aws.cli.cli:info
   :prog: dagster-aws info

.. click:: dagster_aws.cli.cli:init
   :prog: dagster-aws init

.. click:: dagster_aws.cli.cli:shell
   :prog: dagster-aws shell

.. click:: dagster_aws.cli.cli:up
   :prog: dagster-aws up

.. click:: dagster_aws.cli.cli:update_dagster
   :prog: dagster-aws update-dagster
