# Operator-only PharmacoGx 3.16.0 raw-data export. Never evaluates submitted code.
# Fixed invocation: Rscript --vanilla prepare_pharmacogx.R PSET.rds OUTPUT_DIR
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("Expected PSET.rds OUTPUT_DIR")
if (!requireNamespace("PharmacoGx", quietly = TRUE) ||
    as.character(utils::packageVersion("PharmacoGx")) != "3.16.0") {
  stop("Requires PharmacoGx exactly 3.16.0")
}
if (dir.exists(args[[2]]) || file.exists(args[[2]])) stop("Output must be new")
pset <- readRDS(args[[1]]) # Operator-trusted input only; R serialization is not an upload format.
if (!methods::is(pset, "PharmacoSet")) stop("Expected PharmacoSet")
raw <- PharmacoGx::sensitivityRaw(pset)
meta <- as.data.frame(PharmacoGx::sensitivityInfo(pset))
if (length(dim(raw)) != 3L || is.null(dimnames(raw)[[1]]) ||
    !all(c("Dose", "Viability") %in% dimnames(raw)[[3]])) {
  stop("Requires explicit experiment x dose x metric raw array")
}
ids <- dimnames(raw)[[1]]
if (anyDuplicated(ids) || anyDuplicated(rownames(meta)) || !all(ids %in% rownames(meta))) {
  stop("Ambiguous experiment metadata")
}
# Preserve every raw point, including missing values; Python registration rejects incomplete curves.
rows <- do.call(rbind, lapply(ids, function(id) data.frame(
  experiment_id = id, point_index = seq_len(dim(raw)[[2]]),
  dose_source_units = raw[id, , "Dose"], viability_source_scale = raw[id, , "Viability"])))
meta <- cbind(experiment_id = rownames(meta), meta)
dir.create(args[[2]], mode = "0700")
utils::write.csv(rows, file.path(args[[2]], "raw_points.csv"), row.names = FALSE)
utils::write.csv(meta, file.path(args[[2]], "assay_metadata.csv"), row.names = FALSE)
saveRDS(PharmacoGx::sampleInfo(pset), file.path(args[[2]], "sample_metadata.rds"))
saveRDS(PharmacoGx::treatmentInfo(pset), file.path(args[[2]], "treatment_metadata.rds"))
writeLines(c("Adapter: prepare_pharmacogx.v1", "PharmacoGx: 3.16.0",
             paste("Input MD5:", unname(tools::md5sum(args[[1]]))),
             "Units/scales remain source-declared; no fitted AUC or IC50 used.",
             capture.output(utils::sessionInfo())), file.path(args[[2]], "provenance.txt"))
Sys.chmod(list.files(args[[2]], full.names = TRUE), mode = "0600")
