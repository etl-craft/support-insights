ALTER TABLE lnd.client_alpha_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.client_alpha_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.client_alpha_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.client_beta_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.client_beta_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.client_beta_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.client_gamma_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.client_gamma_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.client_gamma_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.steward_ds_agents EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.steward_ds_agents EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.steward_ds_agents EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.steward_ds_customer_types EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.steward_ds_customer_types EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.steward_ds_customer_types EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.steward_ds_support_areas EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.steward_ds_support_areas EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.steward_ds_support_areas EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.steward_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.steward_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.steward_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE lnd.gamma_object_events EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lnd.gamma_object_events EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE lnd.gamma_object_events EXECUTE remove_orphan_files(retention_threshold => '1d');
