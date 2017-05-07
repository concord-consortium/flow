from blocks import createBlock


# represents a data flow diagram
class Diagram(object):

    # create a data flow diagram using a spec dictionary
    def __init__(self, name, diagram_spec):
        self.name = name
        self.blocks = []
        for block_spec in diagram_spec['blocks']:
            self.blocks.append(createBlock(block_spec))

        # set source and destination blocks for each block using source_ids
        for block in self.blocks:
            for source_id in block.source_ids:
                source_block = self.find_block_by_id(source_id)
                source_block.dest_ids.append(block.id)
                block.sources.append(source_block)

    # get a block by ID; returns None if none found
    def find_block_by_id(self, id):
        for block in self.blocks:
            if block.id == id:
                return block
        return None

    # get a block by name; returns None if none found
    # (note: names may not be unique; will return first match)
    def find_block_by_name(self, name):
        for block in self.blocks:
            if block.name == name:
                return block
        return None

    # compute new values for all blocks
    def update(self):

        # mark all blocks as having a stale value
        for block in self.blocks:
            block.stale = True

        # update blocks without destinations;
        # others will get updated recursively
        for block in self.blocks:
            if not block.dest_ids:
                block.update()
