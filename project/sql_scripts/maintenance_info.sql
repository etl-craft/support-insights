ALTER TABLE info.data_dictionary EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE info.data_dictionary EXECUTE expire_snapshots(retention_threshold => '1d');
ALTER TABLE info.data_dictionary EXECUTE remove_orphan_files(retention_threshold => '1d');
