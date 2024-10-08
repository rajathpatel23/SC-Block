import logging

import faiss
import numpy as np
import torch

from src.model.evidence import RetrievalEvidence, AugmentationEvidence
from src.strategy.es_helper import determine_es_index_name
from src.strategy.indexing.faiss_collector import determine_path_to_faiss_index
from src.strategy.indexing.preprocess_records_and_index_es import prepare_processed_action
from src.strategy.retrieval.encoding.bi_encoder_factory import select_bi_encoder
from src.strategy.retrieval.retrieval_strategy import RetrievalStrategy


class QueryByNeuralEntity(RetrievalStrategy):

    def __init__(self, dataset, bi_encoder_name, clusters, model_name, base_model, with_projection, projection, pooling, similarity, without_special_tokens_and_attribute_names=False, switched=False):
        super().__init__(dataset, 'query_by_neural_entity', clusters=clusters, switched=switched)

        logger = logging.getLogger()
        self.pooling = pooling
        self.similarity = similarity
        self.model_name = model_name
        self.switched = switched

        normalize = self.similarity == 'cos'
        bi_encoder_config = {'name': bi_encoder_name, 'model_name': model_name, 'base_model': base_model,
                             'with_projection': with_projection, 'projection': projection,'pooling': pooling,
                             'normalize': normalize}
        self.entity_biencoder = select_bi_encoder(bi_encoder_config, dataset)

        self.rank_evidences_by_table = False
        self.without_special_tokens_and_attribute_names = without_special_tokens_and_attribute_names

        # Load entity representations - TO-DO: Move to central method!
        path_to_faiss_index = determine_path_to_faiss_index(dataset, model_name, pooling, similarity, clusters, switched=switched)
        # if self.clusters:
        #     path_to_faiss_index = '{}/faiss/{}_faiss_{}_{}_{}_with_clusters.index'.format(os.environ['DATA_DIR'], schema_org_class,
        #                                                                     model_name.replace('/', ''), pooling,
        #                                                                     similarity)
        # else:
        #     path_to_faiss_index = '{}/faiss/{}_faiss_{}_{}_{}.index'.format(os.environ['DATA_DIR'], schema_org_class,
        #                                                                 model_name.replace('/', ''), pooling,
        #                                                                 similarity)
        logger.info('Load Faiss index from {}'.format(path_to_faiss_index))
        self.index = faiss.read_index(path_to_faiss_index)

    # Apply Bi-Encoder
    def retrieve_evidence(self, query_table, evidence_count, entity_id):
        logger = logging.getLogger()
        evidence_id = 1
        evidences = []
        entity_vectors = []

        # Iterate through query table and create entity embeddings (neural representations)
        if entity_id is None:
            if query_table.type == 'retrieval':
                entity_vectors = self.entity_biencoder.encode_entities_and_return_pooled_outputs(query_table.table, without_special_tokens_and_attribute_names=self.without_special_tokens_and_attribute_names)
            elif query_table.type == 'augmentation':
                entity_vectors = self.entity_biencoder.encode_entities_and_return_pooled_outputs(query_table.table, [
                    query_table.target_attribute], without_special_tokens_and_attribute_names=self.without_special_tokens_and_attribute_names)
        else:
            for row in query_table.table:
                if entity_id != row['entityId'] and not self.rank_evidences_by_table:
                    continue
                if query_table.type == 'retrieval':
                    pooled_output = self.entity_biencoder.encode_entities_and_return_pooled_outputs([row], without_special_tokens_and_attribute_names=self.without_special_tokens_and_attribute_names)[0]
                elif query_table.type == 'augmentation':
                    pooled_output = self.entity_biencoder.encode_entities_and_return_pooled_outputs([row], [
                        query_table.target_attribute], without_special_tokens_and_attribute_names=self.without_special_tokens_and_attribute_names)[0]
                else:
                    raise ValueError('Query Table Type {} is not defined!'.format(query_table.type))
                entity_vectors.append(pooled_output) # DO NOT CHANGE ORDER OF THIS LIST!

        # Query Faiss index
        torch.cuda.empty_cache()
        entity_vectors = np.array(entity_vectors).astype('float32')
        D, I = self.index.search(entity_vectors, evidence_count)

        # Determine ES Index name
        index_name = determine_es_index_name(self.schema_org_class, clusters=self.clusters, switched=self.switched)

        for i in range(0, len(I)):

            entity_result = self.query_tables_index_by_id(I[i], index_name)

            if self._es is not None:
                hits = [prepare_processed_action(hit) for hit in entity_result['hits']['hits']]
            else:
                hits = entity_result
            # Uncomment following block to make sure that all hits contain the target attribute
            #hits = \
            #    list(filter(lambda hit: query_table.target_attribute in hit['_source'], entity_result['hits']['hits']))

            for hit in hits[:evidence_count]:
                found_value = None
                if query_table.type == 'augmentation' and query_table.target_attribute in hit:
                    # Deal with cases, in which there is not target attribute value
                    found_value = hit[query_table.target_attribute]

                rowId = hit['row_id']
                table_name = hit['table']
                new_entity_id = entity_id if entity_id is not None else query_table.table[i]['entityId']
                if query_table.type == 'retrieval':
                    evidence = RetrievalEvidence(evidence_id, query_table.identifier, new_entity_id,
                                        table_name, rowId, hit)
                elif query_table.type == 'augmentation':
                    evidence = AugmentationEvidence(evidence_id, query_table.identifier, new_entity_id,
                                                 table_name, rowId, hit, found_value, query_table.target_attribute)
                else:
                    raise ValueError('Query Table Type {} is not defined!'.format(query_table.type))

                # Determine similarity
                similarity_not_found = True
                for distance, instance in zip(D[i], I[i]):
                    if int(instance) == int(hit['id']):
                        evidence.scores[self.name] = distance.item()
                        evidence.similarity_score = distance.item()
                        similarity_not_found = False
                        break

                if similarity_not_found:
                    logger.warning('Could not find similarity score for entity {} in faiss index!'.format(hit['_id']))

                evidences.append(evidence)
                self.logger.debug('Added evidence {} to query table'.format(evidence_id))
                evidence_id += 1

        return evidences
