from ....schema.cnlp_types import CNLPTypeToken, TokenTypeOfCNLPTypes
from ....schema.result import Failure, Result

from typing import List, Dict

# 符号的token类型索引
symbol_map = {
    '=': TokenTypeOfCNLPTypes.EQUAL,
    '{': TokenTypeOfCNLPTypes.LBRACE,
    '}': TokenTypeOfCNLPTypes.RBRACE,
    '[': TokenTypeOfCNLPTypes.LBRACKET,
    ']': TokenTypeOfCNLPTypes.RBRACKET,
    ',': TokenTypeOfCNLPTypes.COMMA,
    ':': TokenTypeOfCNLPTypes.COLON,
}

# 关键字（特殊的字符串）的token类型索引
keyword_map = {
    "OPTIONAL": TokenTypeOfCNLPTypes.OPTIONAL,
    "LIST": TokenTypeOfCNLPTypes.LIST,
    "TEXT": TokenTypeOfCNLPTypes.TEXT,
    "NUMBER": TokenTypeOfCNLPTypes.NUMBER,
    "BOOLEAN": TokenTypeOfCNLPTypes.BOOLEAN,
}


class CNLPTypeTokenizer:

    @staticmethod
    def tokenize(cnlp_types_sentence_list: List[dict]) -> Dict[str, List[CNLPTypeToken] | List[Result]]:
        tokens: List[CNLPTypeToken] = []
        # 其实这个error_list中包括的应该是
        error_list = []

        current_sentence_index = 0
        # calculating the amount of all cnlp_types sentence
        total_sentences = len(cnlp_types_sentence_list)

        # avoid out-of-bounds
        while current_sentence_index < total_sentences:
            # line numbers start at "1", indexes start at "0"
            line_number = cnlp_types_sentence_list[current_sentence_index]['line_number']
            sentence = cnlp_types_sentence_list[current_sentence_index]['sentence']
            # 记录光标在当前行所处的位置
            pos = 0
            # 记录当前行的总长度
            length = len(sentence)

            while pos < length:
                character = sentence[pos]

                if character.isspace():
                    pos += 1
                    continue

                # 当遇到引号时，意味着遇到了注释，以下考虑多行注释的情况
                if character == '"':
                    start_line = line_number
                    pos += 1
                    comment = []
                    closed = False

                    while True:
                        while pos < length:
                            # 如果找到了另一个引号，意味着注释结束
                            if sentence[pos] == '"':
                                closed = True
                                pos += 1
                                break
                            comment.append(sentence[pos])
                            pos += 1

                        # 不少情况中，注释的最后一个引号都是在行末出现，所以上面pos < length的循环终止，但是closed又被重置为真。
                        if closed:
                            break

                        # 不然就是多行注释的情况，需要继续向后面的行寻找
                        current_sentence_index += 1

                        # 意味着找注释找到最后一行也没有找到
                        if current_sentence_index == total_sentences:
                            error_list.append(
                                Failure(
                                    value="".join(comment),
                                    is_fatal=False,
                                    message="Missing closing double quote in comment.",
                                    start_line=start_line,
                                    end_line=line_number,
                                    error_type="type_definition_error",
                                )
                            )
                            break

                        sentence = cnlp_types_sentence_list[current_sentence_index]['sentence']
                        line_number = cnlp_types_sentence_list[current_sentence_index]['line_number']
                        pos = 0
                        length = len(sentence)

                        # TODO：应该时不需要加入换行符的
                        # comment.append("\n")
                        # TODO: 在遇到多行注释的情况下时，可能要在行末加一个<space>。
                        comment.append(" ")

                    tokens.append(
                        CNLPTypeToken(
                            token_value="".join(comment),
                            token_type=TokenTypeOfCNLPTypes.COMMENT,
                            start_line=start_line,
                            end_line=line_number,
                        )
                    )

                    # 这个continue非常重要，因为一旦遇到注释，就说明后续不再需要判断该字符的类别了
                    continue

                # 移除了多余的continue！！！

                # 此次开始检测是否为符号类型的字符
                if character in symbol_map:
                    tokens.append(
                        CNLPTypeToken(
                            token_value=character,
                            token_type=symbol_map[character],
                            start_line=line_number,
                            end_line=line_number,
                        )
                    )

                    pos += 1
                    # 此处continue同样是跳过后续Token.type的判断...
                    continue

                # 此处开始检测是否为字符：
                # ".isalnum()'的作用是检测当前值是否属于[0-9] or [a-z, A-Z]
                if character.isalnum() or character == "_":
                    start_pos = pos
                    # 读取完整（即中间不含空格）的字符串
                    while pos < length and (sentence[pos] == "_" or sentence[pos].isalnum()):
                        pos += 1
                    word = sentence[start_pos:pos]

                    if word.upper() in keyword_map:
                        token_type = keyword_map[word.upper()]
                    else:
                        token_type = TokenTypeOfCNLPTypes.WORD

                    tokens.append(
                        CNLPTypeToken(
                            token_value=word,
                            token_type=token_type,
                            start_line=line_number,
                            end_line=line_number,
                        )
                    )

                    continue

                # TODO: Word范围十分广泛，应该不能有识别不到的token类型吧。。。

                # 无效字符处理：添加pos += 1避免死循环
                error_list.append(
                    Failure(
                        value=character,
                        is_fatal=False,
                        message=f"Invalid character: '{character}' in when defining CNL-P types.",
                        start_line=line_number,
                        end_line=line_number,
                        error_type="type_definition_error",
                    )
                )
                # 关键修复：添加pos += 1，避免无效字符导致死循环
                pos += 1

            current_sentence_index += 1

        return {"error_list": error_list, "token_list": tokens}
