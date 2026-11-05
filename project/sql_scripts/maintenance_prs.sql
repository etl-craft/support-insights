ALTER TABLE prs.client_alpha_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE prs.client_alpha_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE prs.client_alpha_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE prs.client_beta_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE prs.client_beta_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE prs.client_beta_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE prs.client_gamma_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE prs.client_gamma_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE prs.client_gamma_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');

ALTER TABLE prs.steward_cs_data EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE prs.steward_cs_data EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE prs.steward_cs_data EXECUTE remove_orphan_files(retention_threshold => '1d');
