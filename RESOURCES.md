# HR Integration Pipeline Resources

## Knowledge

- [Repository README](README.md)
  The intended business context, architecture, rules, outputs, and known limitations. Use for: explaining why the pipeline exists.
- [Golden dataset schema](docs/golden_dataset_schema.md)
  The declared grain, fields, lineage, and validation contract. Use for: checking whether implementation and documentation agree.
- [pandas user guide](https://pandas.pydata.org/docs/user_guide/index.html)
  Official guidance for DataFrame transformations, joins, grouping, missing data, and I/O. Use for: understanding the tabular operations throughout the pipeline.
- [RapidFuzz `fuzz` documentation](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html)
  Official definition of `token_sort_ratio` and its 0-100 similarity score. Use for: explaining review-only name matching.
- [Python `xml.etree.ElementTree` documentation](https://docs.python.org/3/library/xml.etree.elementtree.html)
  Official XML parsing API used by the benefits ingestor. Use for: understanding `parse`, `findall`, tags, and text extraction.
- [Apache Arrow Parquet documentation](https://arrow.apache.org/docs/python/parquet.html)
  Official explanation of columnar Parquet storage and partitioned datasets. Use for: explaining the final dataset layout.

## Wisdom (Communities)

- [Data Engineering Stack Exchange](https://dba.stackexchange.com/questions/tagged/data-warehouse)
  Practitioner discussion of data modeling, quality, lineage, and warehouse tradeoffs. Use for: testing production-design assumptions beyond this capstone.
